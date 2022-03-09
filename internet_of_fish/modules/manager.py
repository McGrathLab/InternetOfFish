import multiprocessing as mp
import os, time, sys, datetime
from glob import glob

import definitions
from detector import Detector
from collector import Collector
from utils import make_logger

class Manager:

    def __init__(self, project_id, model):
        self.logger = make_logger('Manager')
        self.logger.info('initializing manager')

        self.project_id, self.model = project_id, model
        self.vid_dir = os.path.join(definitions.DATA_DIR, project_id, 'Videos')
        self.img_dir = os.path.join(definitions.DATA_DIR, project_id, 'Images')

        self.collector = Collector(self.vid_dir, self.img_dir)
        self.detector = Detector(*self.locate_model_files(model))

    @staticmethod
    def locate_model_files(model):
        try:
            model_path = glob(os.path.join(definitions.MODELS_DIR, model, '*.tflite'))[0]
            label_path = glob(os.path.join(definitions.MODELS_DIR, model, '*.txt'))[0]
            return model_path, label_path
        except IndexError as e:
            print(f'error locating model files:\n{e}')

    def collect_and_detect(self):
        collection_process = self.start_collection()
        detection_process = self.start_detection()
        while collection_process.is_alive() or detection_process.is_alive():
            try:
                time.sleep(10)
                collection_process.join(timeout=0)
                detection_process.join(timeout=0)
            except KeyboardInterrupt:
                print('shutting down detection process')
                self.stop_detection(detection_process)
                print('shutting down collection process')
                self.stop_collection(collection_process)
                print('exiting')
                sys.exit()
            if 8 <= datetime.datetime.now().hour <= 18:
                self.stop_detection(detection_process)
                self.stop_collection(collection_process)


    def start_collection(self):
        self.logger.info('starting collection')
        collection_process = mp.Process(target=self.collector.collect_data)
        collection_process.start()
        return collection_process

    def start_detection(self):
        self.logger.info('starting detection')
        # detection_process = mp.Process(target=self.detector.batch_detect, args=(self.img_dir,))
        detection_process = mp.Process(target=self.detector.queue_detect)
        detection_process.start()
        return detection_process

    def stop_detection(self, detection_process):
        """add a 'STOP' the detector's image queue, which will trigger the detection to exit elegantly"""
        self.detector.img_queue.put('STOP')
        detection_process.join()

    def stop_collection(self, collection_process):
        """add a 'STOP' the collector's signal queue, which will trigger the collection to exit elegantly"""
        self.collector.sig_queue.put('STOP')
        collection_process.join()
