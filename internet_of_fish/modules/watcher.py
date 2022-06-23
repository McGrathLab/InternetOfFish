
import datetime as dt
import socket
import json


class StatusReport:
    def __init__(self, proj_id, curr_mode, curr_procs, last_event):
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
        # generate additional attributes programmatically
        self.disk_usage = float(psutil.disk_usage('/').percent)
        self.mem_usage = float(psutil.virtual_memory().percent)
        self.idle_time = (dt.datetime.now() -
                          recursive_mtime(PROJ_DIR(proj_id))).total_seconds()

    def __call__(self):
        return {key: str(val) for key, val in vars(self).items()}


class WatcherWorker():
    def __init__(self, host_name):
        """This function gets called once, during the class initialization. Any code you would put in __init__ can go
        here, without overriding the boilerplate code from the QueueProcWorker parent class.
        """
        # TODO: Probably set up some of the socket stuff here?
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_host_name = host_name
        self.port_number = 9999  #Make sure this is the server port number


    def main_func(self, item):
        try:
            self.client_socket.connect((self.server_host_name, self.port_number))
        except ConnectionError:
            print("Connection Refused")

        try:
            print('all')
            self.client_socket.sendall(bytes(json.dumps(item), 'utf - 8'))
            print('all')
        except IOError as e:
                pass
