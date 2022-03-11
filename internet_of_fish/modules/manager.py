import multiprocessing as mp
import os, time, sys, datetime
from glob import glob

from internet_of_fish.modules import definitions
from internet_of_fish.modules.detector import start_detection_mp
from internet_of_fish.modules.collector import start_collection_mp
from internet_of_fish.modules.utils import make_logger


class Manager:

    def __init__(self, project_id, model):
        self.logger = make_logger('manager')
        self.logger.info('initializing manager')
        self.definitions = definitions

        self.project_id, self.model = project_id, model
        self.vid_dir = os.path.join(definitions.DATA_DIR, project_id, 'Videos')
        self.img_dir = os.path.join(definitions.DATA_DIR, project_id, 'Images')
        self.img_queue = mp.Queue()
        self.collector_sig_queue = mp.Queue()

        self.detection_process = None
        self.collection_process = None

    @staticmethod
    def locate_model_files(model):
        try:
            model_path = glob(os.path.join(definitions.MODELS_DIR, model, '*.tflite'))[0]
            label_path = glob(os.path.join(definitions.MODELS_DIR, model, '*.txt'))[0]
            return model_path, label_path
        except IndexError as e:
            print(f'error locating model files:\n{e}')

    def collect_and_detect(self, iterlimit=None):
        self.start_collection()
        self.start_detection()
        iters = 0
        while 8 <= datetime.datetime.now().hour <= 18:
            if iterlimit is not None and iters > iterlimit:
                break
            try:
                time.sleep(10)
                self.collection_process.join(timeout=1)
                self.detection_process.join(timeout=1)
            except KeyboardInterrupt:
                print('shutting down detection process')
                self.stop_collection()
                print('shutting down collection process')
                self.stop_detection()
                print('processing and uploading last video')
                self.process_video()
                self.upload_video()
                print('exiting')
                sys.exit()
            iters += 1
            self.logger.debug(f'manager iters = {iters}')
        self.stop_collection()
        self.stop_detection()
        self.process_video()
        self.upload_video()

        while not 7 <= datetime.datetime.now().hour <= 18:
            time.sleep(3600)
        while not 7 <= datetime.datetime.now().hour <= 18:
            time.sleep(1)

        self.collect_and_detect()

    def start_collection(self):
        self.logger.info('starting collection')
        self.collection_process = mp.Process(target=start_collection_mp,
                                             args=(self.vid_dir, self.img_dir, self.img_queue,
                                                   self.collector_sig_queue))
        self.collection_process.daemon = True
        self.collection_process.start()
        return self.collection_process

    def start_detection(self):
        self.logger.info('starting detection')
        self.detection_process = mp.Process(target=start_detection_mp,
                                            args=(*self.locate_model_files(self.model), self.img_queue,))
        self.detection_process.daemon = True
        self.detection_process.start()
        return self.detection_process

    def stop_detection(self):
        """add a 'STOP' the detector's image queue, which will trigger the detection to exit elegantly"""
        if self.detection_process is None:
            self.logger.info('manager.stop_detection called, but no detection process was running')
            return
        self.img_queue.put(('STOP', 'STOP'))
        self.detection_process.join()
        self.detection_process = None

    def stop_collection(self):
        """add a 'STOP' the collector's signal queue, which will trigger the collection to exit elegantly"""
        if self.collection_process is None:
            self.logger.info('manager.stop_collection called, but no collection process was running')
            return
        self.collector_sig_queue.put('STOP')
        self.collection_process.join()
        self.collection_process = None

    def process_video(self):
        # TODO: write this function
        pass

    def upload_video(self):
        # TODO: write this function
        pass


if __name__ == '__main__':
    mp.set_start_method('spawn')
