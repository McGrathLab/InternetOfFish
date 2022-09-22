import os, logging, time
from collections import namedtuple

from glob import glob
import numpy as np
import cv2

from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter, run_inference

import internet_of_fish.modules.utils.advanced_utils
from internet_of_fish.modules import mptools
from internet_of_fish.modules.utils import gen_utils

BufferEntry = namedtuple('BufferEntry', ['cap_time', 'img', 'fish_dets', 'pipe_det'])

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

    def startup(self):
        self.mock_hit_flag = False
        self.pipe_det = []
        self.max_fish = self.metadata['n_fish'] if self.metadata['n_fish'] else self.defs.MAX_DETS
        self.img_dir = self.defs.PROJ_IMG_DIR

        model_paths = glob(os.path.join(self.MODELS_DIR, self.metadata['model_id'], '*.tflite'))
        label_paths = glob(os.path.join(self.MODELS_DIR, self.metadata['model_id'], '*.txt'))

        if len(model_paths) > 1:
            self.logger.info('initializing detector in multi-network mode')
            self.multinet_mode = True
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
        else:
            self.multinet_mode = False
            self.interpreter = make_interpreter(model_paths[0])
            self.interpreter.allocate_tensors()
            self.labels = read_label_file(label_paths[0])
            self.ids = {val: key for key, val in self.labels.items()}

        self.inference_size = common.input_size(self.interpreter)
        self.hit_counter = HitCounter()
        self.avg_timer = gen_utils.Averager()
        self.buffer = []
        self.loop_counter = 0


    def main_func(self, q_item):
        cap_time, img = q_item
        if isinstance(img, str) and (img == 'MOCK_HIT'):
            self.mock_hit_flag = True
            return
        orig_img = cv2.resize(img, self.inference_size)
        inf_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if self.multinet_mode and not self.loop_counter % 100:
            self.update_pipe_location(inf_img)
        dets = self.detect(inf_img)
        fish_dets, pipe_det = self.filter_dets(dets)
        self.buffer.append(BufferEntry(cap_time, orig_img, fish_dets, pipe_det))
        if self.metadata['source']:
            self.overlay_boxes(self.buffer[-1])
        hit_flag = self.check_for_hit(fish_dets, pipe_det)
        self.hit_counter.increment() if hit_flag else self.hit_counter.decrement()
        if self.mock_hit_flag or (self.hit_counter.hits >= self.HIT_THRESH):
            self.mock_hit_flag = False
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
        self.loop_counter += 1
        self.print_info()

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
            self.pipe_det = sorted(new_loc, reverse=True, key=lambda x: x.score)[:1]
            if old_loc:
                iou = detect.BBox.intersect(old_loc[0].bbox, self.pipe_det[0].bbox)
                self.logger.debug(f'pipe location updated. IOU with previous location of {iou}')
            else:
                self.logger.debug(f'pipe location initialized as {self.pipe_det[0].bbox}')

    def detect(self, img, interp=None, update_timer=True):
        """run detection on a single image"""
        if not interp:
            interp = self.interpreter
        start = time.time()
        # _, scale = common.set_resized_input(interp, img.size, lambda size: img.resize(size, Image.ANTIALIAS))
        # interp.invoke()
        run_inference(interp, img.tobytes())
        dets = detect.get_objects(interp, self.defs.CONF_THRESH)
        if update_timer:
            self.avg_timer.update(time.time() - start)
        return dets


    def overlay_boxes(self, buffer_entry: BufferEntry):
        """open an image, draw detection boxes, and replace the original image"""
        # draw = ImageDraw.Draw(buffer_entry.img)
        
        def overlay_box(img_, det_, color_):
            bbox = det_.bbox
            cv2.rectangle(img_, (bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax), color_, 2)
            label = '%s\n%.2f' % (self.labels.get(det_.id, det_.id), det_.score)
            cv2.putText(img_, label,(bbox.xmin + 10, bbox.ymin + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
            
        fish_dets, pipe_det =(buffer_entry.fish_dets, buffer_entry.pipe_det)
        intersect_count = 0
        for det in fish_dets:
            if not pipe_det:
                color = (0, 0, 255)
            else:
                intersect = detect.BBox.intersect(det.bbox, pipe_det[0].bbox)
                intersect_flag = (intersect.valid and np.isclose(intersect.area, det.bbox.area))
                intersect_count += intersect_flag
                color = (0, 255, 0) if intersect_flag else (0, 0, 255)
            overlay_box(buffer_entry.img, det, color)
        if pipe_det:
            color = (0, 0, 255) if not intersect_count else (0, 255, 255) if intersect_count == 1 else (0, 255, 0)
            overlay_box(buffer_entry.img, pipe_det[0], color)
        
        img_path = os.path.join(self.img_dir, f'{buffer_entry.cap_time}.jpg')
        cv2.imwrite(img_path, buffer_entry.img)
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

    def check_for_hit(self, fish_dets, pipe_det):
        """check for multiple fish intersecting with the pipe and adjust hit counter accordingly"""
        if (len(fish_dets) < 2) or (len(pipe_det) != 1):
            return False
        intersect_count = 0
        pipe_det = pipe_det[0]
        for det in fish_dets:
            intersect = detect.BBox.intersect(det.bbox, pipe_det.bbox)
            intersect_count += (intersect.valid and np.isclose(intersect.area, det.bbox.area))
        if intersect_count < 2:
            return False
        else:
            return True

    def filter_dets(self, dets):
        """keep only the the highest confidence pipe detection, and the top n highest confidence fish detections"""
        if not self.multinet_mode:
            fish_dets = [d for d in dets if d.id == self.ids['fish']]
            fish_dets = sorted(fish_dets, reverse=True, key=lambda x: x.score)[:self.max_fish]
            pipe_det = [d for d in dets if d.id == self.ids['pipe']]
            pipe_det = sorted(pipe_det, reverse=True, key=lambda x: x.score)[:1]
            return fish_dets, pipe_det
        else:
            return sorted(dets, reverse=True, key=lambda x: x.score)[:self.max_fish], self.pipe_det



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



