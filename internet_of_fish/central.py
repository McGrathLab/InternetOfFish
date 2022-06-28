#Just something to run watcher.py. Should be replaced by ui.py eventually
from ctypes import sizeof
import sys
import os
import time
from xmlrpc.client import MultiCallIterator

'''
Use two dirname statemets to navigate to parent directories. The abspath 
yields path from InternetOfFish root. The statement behavior is OS dependant
and for Linux and Pis, the below statement is likelier to work

if os.path.abspath(os.path.dirname(os.path.dirname(__file__))) not in sys.path:
    sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
'''
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import modules.watcher as w

class MutliClientCaller():
    def test(self, dummy_client_num):
        
            send_item = w.StatusReport(proj_id="dummyProject", curr_mode="passive",
             curr_procs=["appleProcess", "bananaProcess", "guavaProcess"], last_event="ENTER_ACTIVE_MODE")

            #loop 25 times
            for i in range(dummy_client_num):
                #create sender object from watcherworker
                sender = w.WatcherWorker()
                #connect to server
                sender.startup()
                #send data to server
                sender.main_func(send_item)

m = MutliClientCaller()
m.test(5)


