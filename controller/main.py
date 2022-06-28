import os, sys
import queue
dictDict = {}
from modules.reporter import Reporter
server = Reporter(queue_length=10)
server.accepting_connections(data_dict= dictDict)
