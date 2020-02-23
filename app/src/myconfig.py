import configparser
import os
import threading

def config_lock(func):
    def wrapper(*arg, **kwargs):
        with myconfig._instance_lock:
            return func(*arg, **kwargs)
    return wrapper

class myconfig():
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not hasattr(myconfig, "_instance"):
            with myconfig._instance_lock:
                if not hasattr(myconfig, "_instance"):
                    myconfig._instance = object.__new__(cls)
        return myconfig._instance

    def __init__(self):
        # self._base_path = os.path.dirname(__file__)
        self._base_path = '.'
        self._config_file = '{}/config.ini'.format(self._base_path)
        self._data = configparser.ConfigParser()
        self._data.read(self._config_file)

    @config_lock
    def get(self, section, key):
        return self._data.get(section, key)
