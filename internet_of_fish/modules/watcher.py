from internet_of_fish.modules.mptools import QueueProcWorker
from internet_of_fish.modules.definitions import PROJ_DIR
from internet_of_fish.modules.utils import gen_utils
import datetime as dt
import psutil
import socket
import json


class StatusReport:
    def __init__(self, proj_id, user_email, curr_mode, curr_procs, last_event):
        """
        Simple container class for standardizing and partially automating the status reports that pass between the
        clients and server. Instances of the StatusReport class can be called without arguments to return the instance
        attributes in dictionary form (see Runner.status_report method for a usage example)

        :param proj_id: project id for the currently running project
        :type proj_id: str
        :param curr_mode: the mode (either 'active' or 'passive') of the Runner process
        :type curr_mode: str
        :param curr_procs: list of names of the processes that are currently alive in the main context
        :type curr_procs: list[str]
        :param last_event: msg_type attribute of the most recent mptools.EventMessage object received and processed by
            the runner process (e.g., 'HARD_SHUTDOWN', 'ENTER_ACTIVE_MODE', etc.)
        :type last_event: str
        """
        # store the provided arguments as attributes
        self.proj_id = proj_id
        self.curr_mode = curr_mode
        self.curr_procs = curr_procs
        self.last_event = last_event
        self.user_email = user_email
        # generate additional attributes programmatically
        self.disk_usage = float(psutil.disk_usage('/').percent)
        self.mem_usage = float(psutil.virtual_memory().percent)
        self.idle_time = (dt.datetime.now() -
                          gen_utils.recursive_mtime(PROJ_DIR(proj_id))).total_seconds()
        #get datetime now and format it to string
        self.time_stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)

    def __call__(self):
        return {key: str(val) for key, val in vars(self).items()}


class WatcherWorker(QueueProcWorker, metaclass=gen_utils.AutologMetaclass):

    def startup(self):
        '''
        Initialize the WatcherWorker object with a client object

        Note: According to StackOverflow lore, Python sockets can have occasional
        trouble parsing IPv6
        '''
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_host_name = '127.0.0.1'
        self.port_number = 9999  #Make sure this is the server port number


    def main_func(self, item):
        '''
        Run the main loop of the client. Connects and sends data to server

        :param item: data to be transmitted to the server. Must be serializable.
        :type item: any serializable Python object
        '''
        try:
            self.client_socket.connect((self.server_host_name, self.port_number))
        except ConnectionError:
            print("Connection Refused")

        try:
            self.client_socket.sendall(bytes(json.dumps(item.toJSON()), 'utf - 8'))
        except IOError as ioe:
            print('IO Error', ioe)

    def shutdown(self):
        self.work_q.close()
        self.event_q.close()
