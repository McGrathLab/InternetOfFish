import os, logging, time
from collections import namedtuple

from glob import glob
import cv2
from math import sqrt
import numpy as np

from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.edgetpu import make_interpreter, run_inference

import internet_of_fish.modules.utils.advanced_utils
from internet_of_fish.modules import mptools
from internet_of_fish.modules.utils import gen_utils

BufferEntry = namedtuple('BufferEntry', ['cap_time', 'img', 'fish_dets'])

class HitCounter:

    def __init__(self):
        self.hits = 0.0
        self.decay_rate = 0.25
        self.growth_rate = 1.0

    def increment(self, modifier=1.0):
        self.hits += (self.growth_rate * modifier)

    def decrement(self):
        self.hits = max(0.0, self.hits - self.decay_rate)

    def reset(self):
        self.hits = 0.0


class DetectorWorker(mptools.QueueProcWorker, metaclass=gen_utils.AutologMetaclass):


    def init_args(self, args):
        self.work_q, = args
        self.MODELS_DIR = self.defs.MODELS_DIR
        self.DATA_DIR = self.defs.DATA_DIR
        self.HIT_THRESH = self.defs.HIT_THRESH_SECS // self.defs.INTERVAL_SECS
        self.IMG_BUFFER = self.defs.IMG_BUFFER_SECS // self.defs.INTERVAL_SECS
        self.INTERVAL_SECS = self.defs.INTERVAL_SECS
        self.SAVE_INTERVAL = 3600  # minimum interval between images saved for annotation

    def startup(self):
        self.pipe_det = None
        self.pipe_center = None
        self.pipe_radius = None
        self.force_pipe_update = True
        self.max_fish = self.metadata['n_fish'] if self.metadata['n_fish'] else self.defs.MAX_DETS
        self.img_dir = self.defs.PROJ_IMG_DIR
        self.anno_dir = self.defs.PROJ_ANNO_DIR
        self.count_record = open(os.path.join(self.defs.PROJ_HIT_RECORD_DIR, f'{gen_utils.current_time_iso()}.csv'), 'w')
        self.count_buffer = ['time_ms,count\n']
        self.mock_hit_flag = False

        model_paths = glob(os.path.join(self.MODELS_DIR, self.metadata['model_id'], '*.tflite'))
        fish_model = [m for m in model_paths if 'fish' in os.path.basename(m)]
        pipe_model = [m for m in model_paths if 'pipe' in os.path.basename(m)]
        if not fish_model or not pipe_model:
            self.logger.error(f'multiple tflite files encountered in {self.metadata["model_id"]}, but unable to'
                              f'determine which is the pipe model and which is the fish model. Ensure one model'
                              f'contains "pipe" in its file name, and the other contains "fish"')
            self.event_q.safe_put(mptools.EventMessage(self.name, 'HARD_SHUTDOWN', 'bad model(s)'))
            return
        self.logger.debug(f'using {fish_model[0]} as fish model')
        self.interpreter = make_interpreter(fish_model[0])
        self.interpreter.allocate_tensors()
        self.logger.debug(f'using {pipe_model[0]} as pipe model')
        self.pipe_interpreter = make_interpreter(pipe_model[0])
        self.pipe_interpreter.allocate_tensors()

        self.hit_counter = HitCounter()
        self.avg_timer = gen_utils.Averager()
        self.buffer = []
        self.loop_counter = 0
        self.last_save = None

    def main_func(self, q_item):
        cap_time, img = q_item
        if isinstance(img, str) and (img == 'MOCK_HIT'):
            self.mock_hit_flag = True
            return
        if not self.loop_counter % 100 or not self.pipe_det or self.force_pipe_update:
            self.update_pipe_location(img)
            if not self.pipe_det:
                return
        img = img[self.pipe_det.bbox.ymin:self.pipe_det.bbox.ymax, self.pipe_det.bbox.xmin: self.pipe_det.bbox.xmax]
        fish_dets = sorted(self.detect(img), reverse=True, key=lambda x: x.score)
        fish_dets = self.filter_fish_dets(fish_dets)
        self.buffer.append(BufferEntry(cap_time, img, fish_dets))
        hit_flag = len(fish_dets) >= 2
        if len(fish_dets) >= 1:
            if (
                not self.last_save or
                time.time() - self.last_save >= self.SAVE_INTERVAL or
                (len(fish_dets) >= 2) and time.time() - self.last_save >= self.SAVE_INTERVAL/10
            ):
                self.logger.debug('saving an image for annotation')
                self.save_for_anno(img, cap_time, fish_dets)
        if hit_flag:
            # modifier = sum([(det.score - self.defs.CONF_THRESH) / (1 - self.defs.CONF_THRESH) for det in fish_dets])
            modifier = 1.0
            self.hit_counter.increment(modifier)
            self.logger.debug(f'hit count increased to {self.hit_counter.hits}. {self.HIT_THRESH} required to trigger')
        else:
            self.hit_counter.decrement()
        self.count_buffer.append(f'{cap_time},{self.hit_counter.hits:0.2f}\n')
        if ((self.hit_counter.hits >= self.HIT_THRESH) or self.mock_hit_flag) and (len(self.buffer) >= self.IMG_BUFFER):
            self.logger.info(f"Hit counter reached {self.hit_counter.hits}, possible spawning event")
            img_paths = []
            for be in self.buffer:
                img_paths.append(self.overlay_boxes(be))
                time.sleep(0.1)
            vid_path = self.jpgs_to_mp4(img_paths, 1//self.INTERVAL_SECS)

            # comment the next two lines to disable spawning notifications
            msg = f'possible spawning event in {self.metadata["tank_id"]} at {gen_utils.current_time_iso()}'
            self.event_q.safe_put(mptools.EventMessage(self.name, 'NOTIFY', ['SPAWNING_EVENT', msg, vid_path]))
            self.mock_hit_flag = False
            self.hit_counter.reset()
            self.buffer = []
        if len(self.buffer) > self.IMG_BUFFER:
            self.buffer.pop(0)
        self.loop_counter += 1
        self.print_info()

    def filter_fish_dets(self, fish_dets):
        valid_dets = []
        for det in fish_dets:
            det_center = ((det.bbox.xmax - det.bbox.xmin) / 2, (det.bbox.ymax - det.bbox.ymin) / 2)
            radial_dist = sqrt((det_center[0] - self.pipe_center[0])**2 + (det_center[1] - self.pipe_center[1])**2)
            if radial_dist < self.pipe_radius:
                valid_dets.append(det)
        return valid_dets

    def save_for_anno(self, img, cap_time, fish_dets):
        img_path = os.path.join(self.anno_dir, f'{cap_time}.jpg')
        dets_path = os.path.join(self.anno_dir, f'{cap_time}.txt')
        self.last_save = time.time()
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        cv2.imwrite(img_path, img)
        h, w, _ = img.shape

        with open(dets_path, 'w') as f:
            for bbox in [d.bbox for d in fish_dets]:
                f.write(f'0 {(bbox.xmax+bbox.xmin)/(2*w)} '
                        f'{(bbox.ymax+bbox.ymin)/(2*h)} '
                        f'{(bbox.xmax-bbox.xmin)/w} '
                        f'{(bbox.ymax - bbox.ymin)/h}\n')

    def print_info(self):
        if self.loop_counter == 1 or self.loop_counter == 10 or not self.loop_counter % 100:
            self.logger.info(f'{self.loop_counter} detection loops completed. average deteciton time for last '
                             f'{self.avg_timer.count} loops was {self.avg_timer.avg * 1000}ms')
            self.avg_timer.reset()
            self.write_hit_buffer_to_file()

    def write_hit_buffer_to_file(self):
        self.count_record.writelines(self.count_buffer)
        self.count_buffer = []

    def update_pipe_location(self, img):
        self.logger.debug('updating pipe location')
        new_loc = self.detect(img, interp=self.pipe_interpreter, update_timer=False)
        if not new_loc:
            self.logger.debug('attempted to update pipe location but pipe was not detected. Will try again on next frame')
            self.force_pipe_update = True
            return
        old_loc = self.pipe_det
        self.pipe_det = sorted(new_loc, reverse=True, key=lambda x: x.score)[0]
        self.pipe_center = ((self.pipe_det.bbox.xmax - self.pipe_det.bbox.xmin) / 2,
                            (self.pipe_det.bbox.ymax - self.pipe_det.bbox.ymin) / 2)
        self.pipe_radius = min(self.pipe_det.bbox.width, self.pipe_det.bbox.height) / 2
        if not old_loc:
            self.force_pipe_update = True
            return
        iou = detect.BBox.iou(old_loc.bbox, self.pipe_det.bbox)
        if iou < 0.95:
            self.logger.info(f'low IOU score detected. Pipe locator will rerun until IOU is above 0.95')
            self.force_pipe_update = True
        else:
            self.logger.debug(f'pipe location updated. Confidence of {self.pipe_det.score}.'
                              f' IOU with previous location of {iou}')
            self.force_pipe_update = False

    def detect(self, img, interp=None, update_timer=True):
        """run detection on a single image"""
        if not interp:
            interp = self.interpreter
        start = time.time()
        inf_size = common.input_size(interp)
        scale = (inf_size[1]/img.shape[1], inf_size[0]/img.shape[0])
        img = cv2.resize(img, inf_size)
        run_inference(interp, img.tobytes())
        dets = detect.get_objects(interp, self.defs.CONF_THRESH, scale)
        if update_timer:
            self.avg_timer.update(time.time() - start)
        return dets

    def overlay_boxes(self, buffer_entry: BufferEntry):
        """open an image, draw detection boxes, and replace the original image"""
        
        def overlay_box(img_, det_, color_):
            bbox = det_.bbox
            cv2.rectangle(img_, (bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax), color_, 2)
            label = '%s\n%.2f' % ('fish', det_.score)
            cv2.putText(img_, label,(bbox.xmin + 10, bbox.ymin + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color_, 2)
        img = cv2.cvtColor(buffer_entry.img, cv2.COLOR_RGB2BGR)
        for det in buffer_entry.fish_dets:
            overlay_box(img, det, (0, 255, 0))
        int_pipe_center = (int(np.round(coord)) for coord in self.pipe_center)
        int_pipe_radius = int(np.round(self.pipe_radius))
        cv2.circle(img, int_pipe_center, int_pipe_radius, (0, 255, 0), 2)
        img_path = os.path.join(self.img_dir, f'{buffer_entry.cap_time}.jpg')
        cv2.imwrite(img_path, img)
        return img_path

    def jpgs_to_mp4(self, img_paths, fps=30, delete_jpgs=True):
        """convert a series of jpgs to a single mp4, and (if delete_jpgs) delete the original images"""
        self.logger.debug(f'converting {len(img_paths)} images to a clip at {fps} fps')
        if not img_paths:
            return
        dest_dir = self.defs.PROJ_VID_DIR
        vid_path = internet_of_fish.modules.utils.advanced_utils.jpgs_to_mp4(img_paths, dest_dir, fps)
        if delete_jpgs:
            [os.remove(x) for x in img_paths]
        return vid_path

    def shutdown(self):
        if self.avg_timer.avg:
            self.logger.log(logging.INFO, f'average time for detection loop: {self.avg_timer.avg * 1000}ms')
        if self.metadata['source']:
            self.event_q.safe_put(
                mptools.EventMessage(self.name, 'ENTER_PASSIVE_MODE', f'detection complete, entering passive mode'))
        self.work_q.close()
        self.event_q.close()
        self.count_record.close()



