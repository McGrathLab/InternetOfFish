import multiprocessing as mp
import definitions
import os

from detector import Detector
from collector import Collector
from utils import make_logger

class Manager:

    def __init__(self, vid_dir, img_dir, model_path, label_path):
        self.logger = make_logger('Manager')
        self.logger.info('initializing manager')
        self.img_dir, self.vid_dir = img_dir, vid_dir
        self.collector = Collector(vid_dir, img_dir)
        self.detector = Detector(model_path, label_path)
        self.output = mp.Queue()


    def start_collection(self):
        self.logger.info('starting collection')
        collection_process = mp.Process(target=self.collector.collect_data)
        collection_process.start()
        collection_process.join()

    def start_detection(self):
        self.logger.info('starting detection')
        detection_process = mp.Process(target=self.detector.detect, args=(self.img_dir,))
        detection_process.start()
        detection_process.join()
