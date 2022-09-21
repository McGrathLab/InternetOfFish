import os, logging, time
from collections import namedtuple

from PIL import Image, ImageDraw
from glob import glob
import numpy as np

from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter

import internet_of_fish.modules.utils.advanced_utils
from internet_of_fish.modules import mptools
from internet_of_fish.modules.utils import gen_utils

BufferEntry = namedtuple('BufferEntry', ['cap_time', 'img', 'fish_dets'])

class HitCounter:

    def __init__(self):
        self.hits = 0

    def increment(self):
        self.hits += 1

    def decrement(self):
        if self.hits > 0:
            self.hits -= 1

    def reset(self):
        self.hits = 0


class DetectorWorker(mptools.QueueProcWorker, metaclass=gen_utils.AutologMetaclass):


    def init_args(self, args):
        self.work_q, = args
        self.MODELS_DIR = self.defs.MODELS_DIR
        self.DATA_DIR = self.defs.DATA_DIR
        self.HIT_THRESH = self.defs.HIT_THRESH_SECS / self.defs.INTERVAL_SECS
        self.IMG_BUFFER = self.defs.IMG_BUFFER_SECS / self.defs.INTERVAL_SECS
        self.SAVE_INTERVAL = 60  # minimum interval between images saved for annotation

    def startup(self):
        self.pipe_det = None
        self.max_fish = self.metadata['n_fish'] if self.metadata['n_fish'] else self.defs.MAX_DETS
        self.img_dir = self.defs.PROJ_IMG_DIR
        self.anno_dir = self.defs.PROJ_ANNO_DIR

        model_paths = glob(os.path.join(self.MODELS_DIR, self.metadata['model_id'], '*.tflite'))
        label_paths = glob(os.path.join(self.MODELS_DIR, self.metadata['model_id'], '*.txt'))

        fish_model = [m for m in model_paths if 'fish' in os.path.basename(m)]
        pipe_model = [m for m in model_paths if 'pipe' in os.path.basename(m)]
        fish_labels = [m for m in label_paths if 'fish' in os.path.basename(m)]
        pipe_labels = [m for m in label_paths if 'pipe' in os.path.basename(m)]
        if not fish_model or not pipe_model:
            self.logger.error(f'multiple tflite files encountered in {self.metadata["model_id"]}, but unable to'
                              f'determine which is the pipe model and which is the fish model. Ensure one model'
                              f'contains "pipe" in its file name, and the other contains "fish"')
            self.event_q.safe_put(mptools.EventMessage(self.name, 'HARD_SHUTDOWN', 'bad model(s)'))
            return
        self.interpreter = make_interpreter(fish_model[0])
        self.interpreter.allocate_tensors()
        self.pipe_interpreter = make_interpreter(pipe_model[0])
        self.pipe_interpreter.allocate_tensors()
        self.labels = read_label_file(fish_labels[0])
        self.pipe_labels = read_label_file(pipe_labels[0])
        self.ids = {val: key for key, val in self.labels.items()}

        self.hit_counter = HitCounter()
        self.avg_timer = gen_utils.Averager()
        self.buffer = []
        self.loop_counter = 0
        self.last_save = time.time()


    def main_func(self, q_item):
        cap_time, img = q_item
        if not self.loop_counter % 100 or not self.pipe_det:
            self.update_pipe_location(img)
            if not self.pipe_det:
                return
        img = self.crop_img(img)
        fish_dets = self.detect(img)
        self.buffer.append(BufferEntry(cap_time, img, fish_dets))
        hit_flag = len(fish_dets) >= 2
        if (len(fish_dets) >= 1) and (time.time() - self.last_save >= self.SAVE_INTERVAL):
            self.save_for_anno(img, cap_time)
        self.hit_counter.increment() if hit_flag else self.hit_counter.decrement()
        if self.hit_counter.hits >= self.HIT_THRESH:
            self.logger.info(f"Hit counter reached {self.hit_counter.hits}, possible spawning event")
            img_paths = [self.overlay_boxes(be) for be in self.buffer]
            vid_path = self.jpgs_to_mp4(img_paths)

            # comment the next two lines to disable spawning notifications
            msg = f'possible spawning event in {self.metadata["tank_id"]} at {gen_utils.current_time_iso()}'
            self.event_q.safe_put(mptools.EventMessage(self.name, 'NOTIFY', ['SPAWNING_EVENT', msg, vid_path]))

            self.hit_counter.reset()
            self.buffer = []
        if len(self.buffer) > self.IMG_BUFFER:
            self.buffer.pop(0)
        if self.metadata['source']:
            self.overlay_boxes(self.buffer[-1])
        self.loop_counter += 1
        self.print_info()

    def crop_img(self, img):
        return img.crop([self.pipe_det.bbox.xmin, self.pipe_det.bbox.ymin, self.pipe_det.bbox.xmax, self.pipe_det.bbox.ymax])

    def save_for_anno(self, img, cap_time):
        img_path = os.path.join(self.anno_dir, f'{cap_time}.jpg')
        img.save(img_path)

    def print_info(self):
        if not self.loop_counter % 100:
            self.logger.info(f'{self.loop_counter} detection loops completed. current average detection time is '
                             f'{self.avg_timer.avg * 1000}ms')

    def update_pipe_location(self, img):
        new_loc = self.detect(img, interp=self.pipe_interpreter, update_timer=False)
        if not new_loc:
            self.logger.debug('attempted to update pipe location but pipe was not detected. keeping old location')
            return
        else:
            old_loc = self.pipe_det
            self.pipe_det = sorted(new_loc, reverse=True, key=lambda x: x.score)[0]
            if old_loc:
                iou = detect.BBox.intersect(old_loc.bbox, self.pipe_det.bbox)
                self.logger.debug(f'pipe location updated. IOU with previous location of {iou}')
            else:
                self.logger.debug(f'pipe location initialized as {self.pipe_det.bbox}')

    def detect(self, img, interp=None, update_timer=True):
        """run detection on a single image"""
        if not interp:
            interp = self.interpreter
        start = time.time()
        _, scale = common.set_resized_input(interp, img.size, lambda size: img.resize(size, Image.ANTIALIAS))
        interp.invoke()
        dets = detect.get_objects(interp, self.defs.CONF_THRESH, scale)
        if update_timer:
            self.avg_timer.update(time.time() - start)
        return dets

    def overlay_boxes(self, buffer_entry: BufferEntry):
        """open an image, draw detection boxes, and replace the original image"""     
        draw = ImageDraw.Draw(buffer_entry.img)
        
        def overlay_box(det_, color_):
            bbox = det_.bbox
            draw.rectangle([(bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax)],
                           outline=color_)
            draw.text((bbox.xmin + 10, bbox.ymin + 10),
                      '%s\n%.2f' % (self.labels.get(det_.id, det_.id), det_.score),
                      fill=color_)

        for det in buffer_entry.fish_dets:
            overlay_box(det, 'green')
        
        img_path = os.path.join(self.img_dir, f'{buffer_entry.cap_time}.jpg')
        buffer_entry.img.save(img_path)
        return img_path

    def jpgs_to_mp4(self, img_paths, delete_jpgs=True):
        """convert a series of jpgs to a single mp4, and (if delete_jpgs) delete the original images"""
        if not img_paths:
            return
        dest_dir = self.defs.PROJ_VID_DIR
        vid_path = internet_of_fish.modules.utils.advanced_utils.jpgs_to_mp4(img_paths, dest_dir, 1 // self.defs.INTERVAL_SECS)
        if delete_jpgs:
            [os.remove(x) for x in img_paths]
        return vid_path


    def shutdown(self):
        if self.avg_timer.avg:
            self.logger.log(logging.INFO, f'average time for detection loop: {self.avg_timer.avg * 1000}ms')
        if self.metadata['source']:
            self.jpgs_to_mp4(glob(os.path.join(self.img_dir, '*.jpg')))
        if self.metadata['demo'] or self.metadata['source']:
            self.event_q.safe_put(
                mptools.EventMessage(self.name, 'ENTER_PASSIVE_MODE', f'detection complete, entering passive mode'))
        self.work_q.close()
        self.event_q.close()



