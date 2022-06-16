# TODO: write reporter script
"""this script takes in status information from multiple pi's via socket connections to their watcher processes,
parse those status reports, and compile them into a human-readable format/file (possibly a file that is read-only
to the user, but writeable by this program?).

Should also notice when a particular host suddenly stops pinging, and potentially notify someone? probably easiest to
have the status reports include the email associated with each project, and set up a simple sendgrid notifier.

https://realpython.com/python-sockets/
"""
# import os, sys, inspect
# currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
# print(currentdir)
# parentdir = os.path.dirname(currentdir)
# grandparentdir = os.path.dirname(parentdir)

# sys.path.insert(0, parentdir)

import socket
import json
import selectors

server_host_name = socket.gethostbyname(socket.gethostname())
port_number = 13221 #Make sure this is the server port number


class Reporter():
    def __init__(self):
        self.listening_socket = socket.socket(socket.AF_INET,
                                              socket.SOCK_STREAM)
        self.listening_socket.bind((server_host_name, port_number))
        connection_queue_length = 50 #the number of connections that can be held in queue before the system panics
        self.listening_socket.listen(connection_queue_length)
        self.listening_socket.setblocking(False)
        sel = selectors.DefaultSelector()
        sel.register(self.listening_socket, selectors.EVENT_READ, data=None)
        print(server_host_name)

    def main_func(self):
        """
        I saw little value in two functions: main_loop and this one because the server listens in a loop
        by its nature. Thus, everything important is here.

        Returns the dictionary data
        """
        serial_data = ''
        conn, addr = self.listening_socket.accept()
        while True:
            print('connected with ', addr)
            data = conn.recv(4096).decode('utf-8')
            serial_data += data
            print(json.loads(serial_data))
       

