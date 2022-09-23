import logging, os, time
from internet_of_fish.modules import mptools
from internet_of_fish.modules.utils import gen_utils
import cv2
import datetime as dt
from math import ceil


class CollectorWorker(mptools.ProcWorker, metaclass=gen_utils.AutologMetaclass):


    def init_args(self, args):
        self.img_q, = args
        self.INTERVAL_MSECS = self.defs.INTERVAL_SECS * 1000
        self.FRAMERATE = self.defs.FRAMERATE  # pi camera framerate
        self.MAX_VID_LEN = self.defs.MAX_VID_LEN  # max length of an individual video (in hours)

    def startup(self):
        self.cap = self.get_cap_obj()
        self.RESOLUTION = (int(self.cap.get(3)), int(self.cap.get(4)))
        self.cap.set(cv2.CAP_PROP_FPS, self.FRAMERATE)
        self.vid_dir = self.defs.PROJ_VID_DIR
        self.writer = cv2.VideoWriter(self.generate_vid_path(),
                                      cv2.VideoWriter_fourcc(*'XVID'),
                                      self.FRAMERATE,
                                      self.RESOLUTION)
        self.last_split = dt.datetime.now().hour
        self.last_det = gen_utils.current_time_ms()

    def get_cap_obj(self):
        return cv2.VideoCapture(0)

    def main_func(self):
        cap_time = gen_utils.current_time_ms()
        ret, img = self.cap.read()
        self.writer.write(img)
        if cap_time - self.last_det >= self.INTERVAL_MSECS:
            img = cv2.resize(img, (img.shape[1]//2, img.shape[0]//2))
            self.img_q.safe_put((cap_time, img))
        if self.MAX_VID_LEN and (dt.datetime.now().hour - self.last_split >= self.MAX_VID_LEN):
            self.split_recording()

    def shutdown(self):
        self.cap.release()
        self.writer.release()
        self.img_q.safe_put('END')
        self.img_q.close()
        self.event_q.close()

    def generate_vid_path(self):
        return os.path.join(self.vid_dir, f'{gen_utils.current_time_iso()}.avi')

    def split_recording(self):
        # self.cam.split_recording(self.generate_vid_path())
        self.writer.release()
        self.writer = cv2.VideoWriter(self.generate_vid_path())
        self.last_split = dt.datetime.now().hour


class SourceCollectorWorker(CollectorWorker):

    """functions like a CollectorWorker, but gathers images from an existing file rather than a camera"""

    def init_args(self, args):
        self.img_q, self.video_file = args
        self.INTERVAL_SECS = self.defs.INTERVAL_SECS
        self.INTERVAL_MSECS = self.INTERVAL_SECS * 1000
        self.MAX_VID_LEN = self.defs.MAX_VID_LEN  # max length of an individual video (in hours)

    def startup(self):
        if not os.path.exists(self.video_file):
            self.locate_video()
        self.cap = cv2.VideoCapture(self.video_file)
        self.RESOLUTION = (int(self.cap.get(3)), int(self.cap.get(4)))
        self.FRAMERATE = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.cap_rate = max(1, int(ceil(self.FRAMERATE * self.INTERVAL_SECS)))
        self.logger.log(logging.INFO, f"Collector will add an image to the queue every {self.cap_rate} frame(s)")
        self.frame_count = 0
        self.active = True

    def main_func(self):
        if not self.active:
            time.sleep(1)
            return
        ret, img = self.cap.read()
        cap_time = gen_utils.current_time_ms()
        if ret:
            img = cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2))
            put_result = self.img_q.safe_put((cap_time, img))
            while not put_result:
                time.sleep(1)
                put_result = self.img_q.safe_put((cap_time, img))
            self.frame_count += self.cap_rate
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_count)
        else:
            self.active = False
            self.logger.log(logging.INFO, "VideoCollector entering sleep mode (no more frames to process)")
            self.img_q.safe_put('END_WARNING')
            self.img_q.safe_put('END')

    def locate_video(self):
        path_elements = [self.defs.HOME_DIR,
                         * os.path.relpath(self.defs.DATA_DIR, self.defs.HOME_DIR).split(os.sep),
                         self.metadata['proj_id'],
                         'Videos']
        for i in range(len(path_elements)):
            potential_path = os.path.join(*path_elements[:i+1], self.video_file)
            self.logger.debug(f'checking for video in {potential_path}')
            if os.path.exists(potential_path):
                self.video_file = potential_path
                break
            self.logger.debug('no video found')
        if not os.path.exists(self.video_file):
            self.logger.log(logging.ERROR, f'failed to locate video file {self.video_file}. '
                                           f'Try placing it in {self.defs.HOME_DIR}')
            raise FileNotFoundError

    def shutdown(self):
        self.cap.release()
        self.img_q.close()
        self.event_q.close()


class SimpleCollectorWorker(CollectorWorker):

    def init_args(self, args):
        if args:
            raise ValueError(f"Unexpected arguments to ProcWorker.init_args: {args}")
        self.FRAMERATE = self.defs.FRAMERATE  # pi camera framerate
        self.RESOLUTION = (int(self.cap.get(3)), int(self.cap.get(4)))
        self.MAX_VID_LEN = self.defs.MAX_VID_LEN  # max length of an individual video (in hours)
        self.INTERVAL_SECS = self.defs.INTERVAL_SECS

    def main_func(self):
        ret, img = self.cap.read()
        self.writer.write(img)
        if self.MAX_VID_LEN and (dt.datetime.now().hour - self.last_split >= self.MAX_VID_LEN):
            self.split_recording()

    def shutdown(self):
        self.cam.stop_recording()
        self.cam.close()
        self.event_q.close()


class DepthCollectorWorker(CollectorWorker):
    # TODO: write a collector worker that collects video and depth (but not images)
    pass
