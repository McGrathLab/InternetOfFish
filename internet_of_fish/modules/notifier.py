from internet_of_fish.modules.mptools import QueueProcWorker

class NotifierWorker(QueueProcWorker):

    def startup(self):
        pass

    def main_func(self):
        pass

    def shutdown(self):
        self.work_q.close()
        self.event_q.close()

