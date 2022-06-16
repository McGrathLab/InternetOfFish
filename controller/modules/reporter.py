import socket
import sys
import json

all_connections = []
all_address = []

class Reporter():
    def __init__(self):
        self.create_socket()
        self.bind_socket()

    def create_socket(self):
        try:
            global host
            global port
            global s
            host = socket.gethostbyname(socket.gethostname())
            port = 9999
            s = socket.socket()

        except socket.error as msg:
            print("Socket creation error: " + str(msg))


    # Binding the socket and listening for connections
    def bind_socket(self):
        try:
            global host
            global port
            global s
            print(host)
            s.bind((host, port))
            s.listen(5)

        except socket.error as msg:
            print("Socket Binding error" + str(msg) + "\n" + "Retrying...")
            bind_socket()


    # Handling connection from multiple clients and saving to a list
    # Closing previous connections when server.py file is restarted

    def accepting_connections(self):
        for c in all_connections:
            c.close()

        del all_connections[:]
        del all_address[:]

        while True:
            try:
                conn, address = s.accept()
                s.setblocking(True)  # prevents timeout

                print("Connection has been established :" + address[0])
                serial_data = ''
                data = conn.recv(4096).decode('utf-8')
                serial_data += data
                print(json.loads(serial_data))
            except:
                print("Error accepting connections")

