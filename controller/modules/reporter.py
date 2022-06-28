
from audioop import add
import socket
import sys
import json

all_addresses = []

class Reporter():
    def __init__(self, queue_length):

        #create
        try:
            '''
            i am testing this one mac which has an old macOS related issue. when using for linux
             or macOS bigSur or later,more robust method gethostname() can be usd instead of 'localhost'
            '''
            self.host = socket.gethostbyname('localhost') 
            self.port = 9999
            self.server = socket.socket()
            print(self.host)
        except socket.error as msg:
            print("Socket creation error: " + str(msg))

        #bind
        try:
            self.server.bind((self.host, self.port))
            self.server.listen(queue_length)
        except socket.error as msg:
            print("Socket Binding error" + str(msg) + "\n" + "Retrying...")


    # Handling connection from multiple clients and saving to a list
    # Closing previous connections when server.py file is restarted

    def accepting_connections(self, data_dict):
        #cleaning data of clients from the last time the server was working
        del all_addresses[:]

        #Keep ears open for connections fro clients and receive data
        while True:
            try:
                conn, address = self.server.accept()
                self.server.setblocking(True)  #finishes dealing with one client before accepting another
                print("Connection has been established :" + address[0])
                serial_data = ''
                #create a record of any new connection using unique IP-port number combination
                if address not in all_addresses:
                    all_addresses.append(address)
                    data_dict[address] = []
                #keep receiving data until there is none left
                while True:
                    data = conn.recv(1024)
                    if data:
                        serial_data += data.decode('utf-8')
                    else:
                        break
                conn.close()
                #deserialize and record the data
                data_dict[address].append(json.loads(serial_data))
                print(data_dict)
            except Exception as e:
                print("Error accepting connections", e)
  
