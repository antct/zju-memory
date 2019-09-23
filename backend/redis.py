import threading
import datetime
import os

def redis_lock(func):
    def wrapper(*arg, **kwargs):
        with redis._instance_lock:
            return func(*arg, **kwargs)
    return wrapper

class redis():
    _instance_lock = threading.Lock()
    def __new__(cls, *args, **kwargs):
        if not hasattr(redis, "_instance"):
            with redis._instance_lock:
                if not hasattr(redis, "_instance"):
                    redis._instance = object.__new__(cls)
        return redis._instance

    def __init__(self, path='./redis/'):
        # if redis save dir not exists, mkdir
        if not os.path.exists(path):
            os.mkdir(path)
        self._path = path

    @redis_lock
    def setex(self, key, value, ex):
        # ./redis/token

        now_time = datetime.datetime.now()
        delta = datetime.timedelta(seconds=ex)
        expire_time = (now_time + delta).strftime('%Y-%m-%d %H:%M:%S')

        to_dict = {
            'key': str(value),
            'time': expire_time
        }

        with open('{}{}'.format(self._path, key), "w+") as wf:
            wf.write(str(to_dict))

    @redis_lock
    def getex(self, key):
        key_path = '{}{}'.format(self._path, key)

        # no save
        if not os.path.exists(key_path):
            return None

        content = None
        with open(key_path, 'r') as f:
            content = eval(f.read())

        value = content['key']
        expire_time = content['time']

        expire_time = datetime.datetime.strptime(expire_time, "%Y-%m-%d %H:%M:%S")
        now_time = datetime.datetime.now()

        # expire
        if now_time > expire_time:
            os.remove(key_path)
            return None
        else:
            return value
