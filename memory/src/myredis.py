import threading
import datetime
import os
import redis

# base_path = os.path.dirname(__file__)
base_path = '.'

# redis lock wrapper for safe thread
def redis_lock(func):
    def wrapper(*arg, **kwargs):
        with myredis._instance_lock:
            return func(*arg, **kwargs)
    return wrapper

# why need this class?
# I have no root permission...
class myredis():

    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not hasattr(myredis, "_instance"):
            with myredis._instance_lock:
                if not hasattr(myredis, "_instance"):
                    myredis._instance = object.__new__(cls)
        return myredis._instance

    def __init__(self, path='{}/redis/'.format(base_path), key_prefix='normal_', redis_type=1):
        # if redis save dir not exists, mkdir
        # actually here need thread, but singleon
        self._key_prefix = key_prefix
        self._redis_type = redis_type
        if self._redis_type == 0:
            if not os.path.exists(path):
                os.mkdir(path)
            self._path = path
        else:
            self._conn = redis.Redis(
                host='127.0.0.1',
                port=6379,
                db=1,
                decode_responses=True
            )

    @redis_lock
    def setex(self, key, value, ex=None):
        # set key and value with expire time
        key = self._key_prefix + key
        if self._redis_type == 0:
            current_time = datetime.datetime.now()
            if ex:
                time_delta = datetime.timedelta(seconds=ex)
                expire_time = (current_time + time_delta).strftime('%Y-%m-%d %H:%M:%S')
            else:
                expire_time = None
            save_dict = {
                'value': str(value),
                'time': expire_time
            }
            with open('{}{}'.format(self._path, key), "w+") as wf:
                wf.write(str(save_dict))
        else:
            self._conn.set(key, value, ex=ex)

    @redis_lock
    def getex(self, key):
        key = self._key_prefix + key
        if self._redis_type == 0:
            key_path = '{}{}'.format(self._path, key)
            # not found
            if not os.path.exists(key_path):
                return None
            # found
            with open(key_path, 'r') as f:
                try:
                    save_dict = eval(f.read())
                except Exception:
                    return None
            value = save_dict['value']
            expire_time = save_dict['time']

            if not expire_time:
                return value

            expire_time = datetime.datetime.strptime(expire_time, "%Y-%m-%d %H:%M:%S")
            current_time = datetime.datetime.now()
            # expire
            if current_time > expire_time:
                os.remove(key_path)
                return None
            # not expire
            else:
                return value
        else:
            # return the value at key name, or None if the key doesn't exist
            return self._conn.get(key)

    @redis_lock
    def exists(self, key):
        key = self._key_prefix + key
        if self._redis_type == 0:
            key_path = '{}{}'.format(self._path, key)
            # not found
            if not os.path.exists(key_path):
                return False
            # found
            with open(key_path, 'r') as f:
                try:
                    save_dict = eval(f.read())
                except Exception:
                    return None
            expire_time = save_dict['time']

            if not expire_time:
                return True

            expire_time = datetime.datetime.strptime(expire_time, "%Y-%m-%d %H:%M:%S")
            current_time = datetime.datetime.now()
            # expire
            if current_time > expire_time:
                os.remove(key_path)
                return False
            # not expire
            else:
                return True
        else:
            return self._conn.exists(key)

    @redis_lock
    def delete(self, key):
        key = self._key_prefix + key
        if self._redis_type == 0:
            key_path = '{}{}'.format(self._path, key)
            # not found
            if not os.path.exists(key_path):
                return 
            # found
            os.remove(key_path)
        else:
            return self._conn.delete(key)

    @redis_lock
    def inc(self, key, step=1):
        key = self._key_prefix + key
        if self._redis_type == 0:
            key_path = '{}{}'.format(self._path, key)
            try:
                with open(key_path, 'r') as f:
                    old_value = int(eval(f.read())['value'])
            except Exception:
                old_value = 0

            new_value = old_value + step
            save_dict = {
                'value': str(new_value),
            }
            with open('{}{}'.format(self._path, key), "w+") as wf:
                wf.write(str(save_dict))
        else:
            new_value = self._conn.incr(key, amount=step)
        return new_value
