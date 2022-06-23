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
        '''
        Create a server socket and set global parameters for initialization
        '''
        try:
            global host
            global port
            global s
            host = socket.gethostbyname(socket.gethostname())
            port = 9999 #very unlikely not to work. If it doesn't, just put random 4 digit numbers above 1024 until it works
            s = socket.socket()

        except socket.error as msg:
            print("Socket creation error: " + str(msg))


    # Binding the socket and listening for connections
    def bind_socket(self):
        '''
        Bind the server socket to the local IP and  given port number
        '''
        try:
            global host
            global port
            global s
            print(host)
            s.bind((host, port))
            s.listen(5)

        except socket.error as msg:
            print("Socket Binding error" + str(msg) + "\n" + "Retrying...")


    # Handling connection from multiple clients and saving to a list
    # Closing previous connections when server.py file is restarted

    def accepting_connections(self, dict_list):
        #close all existing connections
        for c in all_connections:
            c.close()
        #cleaning data of clients from the last time the server was working
        del all_connections[:]
        del all_address[:]

        #Keep ears open for connections fro clients and receive data
        while True:
            try:
                conn, address = s.accept()
                s.setblocking(True)  # prevents timeout
                print("Connection has been established :" + address[0])
                serial_data = ''
                data = conn.recv(4096).decode('utf-8') #It will throw away any data beyond 4096 bytes
                serial_data += data
                dict_list.append(json.loads(serial_data))
            except:
                print("Error accepting connections")
    
    def get_addresses(self):
        '''
        Returns connection addresses of all the clients
        '''
        return all_address