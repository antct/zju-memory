import threading

def pool_lock(func):
    def wrapper(*arg, **kwargs):
        with pool._instance_lock:
            return func(*arg, **kwargs)
    return wrapper

class pool():
    _instance_lock = threading.Lock()
    _max_size = 100
    _obj_pool = {}
    def __new__(cls, *args, **kwargs):
        if not hasattr(pool, "_instance"):
            with pool._instance_lock:
                if not hasattr(pool, "_instance"):
                    pool._instance = object.__new__(cls)
        return pool._instance

    def __init__(self):
        pass

    @pool_lock
    def save(self, id, obj):
        pool._obj_pool[id] = obj

    @pool_lock
    def get(self, id):
        return pool._obj_pool[id]

    @pool_lock
    def delete(self, id):
        pool._obj_pool.pop(id)

    @pool_lock
    def clear(self):
        pool._obj_pool.clear()

    @pool_lock
    def keys(self):
        return list(pool._obj_pool.keys())

    @pool_lock
    def delete_id(self, id):
        pool._obj_pool.pop(id)


    @pool_lock
    def exists(self, username):
        return username in list(pool._obj_pool.keys())

    @pool_lock
    def empty(self):
        return not len(pool._obj_pool)