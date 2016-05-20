from flask import Flask, send_from_directory
from flask.ext.script import Manager

class ZtpWebApp(object):
    def __init__(self):
        self.app = Flask('aeon-ztp', static_url_path='')
        self.manager = Manager(self.app)

Ztp = ZtpWebApp()
app = Ztp.app
manager = Ztp.manager
