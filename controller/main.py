import os, sys



from modules.reporter2 import Reporter2

if os.path.abspath(os.path.dirname(os.path.dirname(__file__))) not in sys.path:
    sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

server = Reporter2()
server.accepting_connections()
