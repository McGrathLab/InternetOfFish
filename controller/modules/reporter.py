import os
from audioop import add
import socket
import sys
import json
import datetime as dt
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import ast

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
        last_check = dt.datetime.now()
        #Keep ears open for connections fro clients and receive data
        while True:
            try:
                conn, address = self.server.accept()
                self.server.setblocking(True)  #finishes dealing with one client before accepting another
                print("Connection has been established :" + address[0])
                serial_data = ''

                if address not in all_addresses:
                    all_addresses.append(address)
                    data_dict[address] = []

                if dt.datetime.now() - last_check > dt.timedelta(seconds=5):
                    try:
                        last_check = dt.datetime.now()
                        print("Checking for clients...")
                        for address in data_dict.keys():
                            if (len(data_dict[address]) == 0) or (data_dict[address][len(data_dict[address]) - 1] == 'email sent'):
                                continue
                            else:
                                last_stamp = dt.datetime.strptime(((data_dict[address])[len(data_dict[address]) - 1])['time_stamp'], "%Y-%m-%d %H:%M:%S")
                                if last_check - last_stamp > dt.timedelta(seconds=5):
                                    data_dict[address].append('email sent')
                                    print("Sending email to " + str(address))
                                    #self.send_email(data_dict, address)
                    except Exception as e:
                        print(e)

                #keep receiving data until there is none left
                while True:
                    data = conn.recv(1024)
                    if data:
                        serial_data += data.decode('utf-8')
                    else:
                        break
                conn.close()
                #deserialize and record the data
                data_dict[address].append(ast.literal_eval(json.loads(serial_data)))
                print(data_dict)
            except Exception as e:
                print("Error accepting connections", e)
    
    def send_email(self, data_dict, address):
        to_send = json.dumps(data_dict[address][len(data_dict[address]) - 1])
        message = Mail(from_email='chinarshital@gmail.com',
         to_emails=data_dict[address][len(data_dict[address]) - 1]['user_email'],
          subject='McGrathLab - a Pi is down!', plain_text_content=to_send)

        try:
            sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY')) #requires some setup, check https://pypi.org/project/sendgrid/
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.message)
  