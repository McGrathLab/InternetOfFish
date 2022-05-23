# TODO: write reporter script
"""this script takes in status information from multiple pi's via socket connections to their watcher processes,
parse those status reports, and compile them into a human-readable format/file (possibly a file that is read-only
to the user, but writeable by this program?).

Should also notice when a particular host suddenly stops pinging, and potentially notify someone? probably easiest to
have the status reports include the email associated with each project, and set up a simple sendgrid notifier.

https://realpython.com/python-sockets/

"""

from internet_of_fish.modules.utils import gen_utils
import socket
import pickle

server_host_name = '127.0.0.1' #Make sure this is the server IP address
port_number = 13221 #Make sure this is the server port number


class Reporter(metaclass=gen_utils.AutologMetaclass):
    def __init__(self):
        self.listening_socket = socket.socket(socket.AF_INET,
                                              socket.SOCK_STREAM)
        self.listening_socket.bind((server_host_name, port_number))

    def main_func(self):
        """
        I saw little value in two functions: main_loop and this one because the server listens in a loop
        by its nature. Thus, everything important is here.

        Returns the dictionary data
        """
        serial_data = ''

        connection_queue_length = 50 #the number of connections that can be held in queue before the system panics
        self.listening_socket.listen(connection_queue_length)

        while True:
            conn, addr = self.listening_socket.accept()
            data = conn.recv(1024)
            if not data:
                break
            serial_data += data
        return pickle.loads(serial_data)
