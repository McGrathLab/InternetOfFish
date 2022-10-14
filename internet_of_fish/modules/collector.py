import logging, os, time
from internet_of_fish.modules import mptools
from internet_of_fish.modules.utils import gen_utils
import cv2
import datetime as dt
from math import ceil
import picamera
import numpy as np

class CollectorWorker(mptools.TimerProcWorker, metaclass=gen_utils.AutologMetaclass):

    def init_args(self, args):
        self.img_q, = args
        self.INTERVAL_SECS = self.defs.INTERVAL_SECS
        self.FRAMERATE = self.defs.FRAMERATE  # pi camera framerate
        self.RESOLUTION = (self.defs.H_RESOLUTION, self.defs.V_RESOLUTION) # pi camera resolution
        self.MAX_VID_LEN = self.defs.MAX_VID_LEN  # max length of an individual video (in hours)

    def startup(self):
        self.cam = self.init_camera()
        self.vid_dir = self.defs.PROJ_VID_DIR
        self.cam.start_recording(self.generate_vid_path())
        self.last_split = dt.datetime.now().hour
        self.last_det = gen_utils.current_time_ms()
        self.resize_resolution = self.calc_resize_resolution()
        self.resize_resolution_flat = self.resize_resolution[0] * self.resize_resolution[1] * 3

    def init_camera(self):
        cam = picamera.PiCamera()
        cam.resolution = self.RESOLUTION
        cam.framerate = self.FRAMERATE
        return cam

    def calc_resize_resolution(self):
        """Calculate the downsized resolution as 1/2 of the original resolution rounded up to the nearest multiple of
        32 (horizontally) and 16 (vertically)"""
        hres_old, vres_old = self.RESOLUTION
        hres_new = gen_utils.mround_up(hres_old/2, 32)
        vres_new = gen_utils.mround_up(vres_old/2, 16)
        return hres_new, vres_new

    def main_func(self):
        cap_time = gen_utils.current_time_ms()
        image = np.empty((self.resize_resolution_flat,), dtype=np.uint8)
        self.cam.capture(image, format='bgr', use_video_port=True, resize=self.resize_resolution)
        image = image.reshape((240, 320, 3))
        self.img_q.safe_put((cap_time, image))
        if self.MAX_VID_LEN and (dt.datetime.now().hour - self.last_split >= self.MAX_VID_LEN):
            self.split_recording()

    def shutdown(self):
        self.cam.stop_recording()
        self.cam.close()
        self.img_q.safe_put('END')
        self.img_q.close()
        self.event_q.close()

    def generate_vid_path(self):
        return os.path.join(self.vid_dir, f'{gen_utils.current_time_iso()}.h264')

    def split_recording(self):
        # self.cam.split_recording(self.generate_vid_path())
        self.cam.split_recording(self.generate_vid_path())
        self.last_split = dt.datetime.now().hour


class SourceCollectorWorker(CollectorWorker):

    """functions like a CollectorWorker, but gathers images from an existing file rather than a camera"""

    def init_args(self, args):
        self.img_q, self.video_file = args
        self.INTERVAL_SECS = self.defs.INTERVAL_SECS
        self.INTERVAL_MSECS = self.INTERVAL_SECS * 1000

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
        self.INTERVAL_SECS = self.defs.INTERVAL_SECS
        self.RESOLUTION = (self.defs.H_RESOLUTION, self.defs.V_RESOLUTION)  # pi camera resolution
        self.FRAMERATE = self.defs.FRAMERATE  # pi camera framerate
        self.MAX_VID_LEN = self.defs.MAX_VID_LEN

    def main_func(self):
        time.sleep(5)
        if self.MAX_VID_LEN and (dt.datetime.now().hour - self.last_split >= self.MAX_VID_LEN):
            self.split_recording()
            self.last_split = dt.datetime.now().hour

    def shutdown(self):
        self.cam.stop_recording()
        self.cam.close()
        self.event_q.close()


class DepthCollectorWorker(CollectorWorker):
    # TODO: write a collector worker that collects video and depth (but not images)
    pass
