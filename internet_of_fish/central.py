#Just something to run watcher.py. Should be replaced by ui.py eventually
import sys
import os

'''
Use two dirname statemets to navigate to parent directories. The abspath 
yields path from InternetOfFish root. The statement behavior is OS dependant
and for Linux and Pis, the below statement is likelier to work

if os.path.abspath(os.path.dirname(os.path.dirname(__file__))) not in sys.path:
    sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
'''
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from internet_of_fish.modules.watcher import WatcherWorker

x = {1:'a'}
WatcherWorker.startup()
WatcherWorker.main_func(item = x)
