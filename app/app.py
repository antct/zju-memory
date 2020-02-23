from flask import Flask, render_template
from src.core import zju
from src.pool import pool
from src.myredis import myredis
from src.myconfig import myconfig

app = Flask(__name__, template_folder='html')

myredis = myredis(redis_type=0)
myconfig = myconfig()

username = myconfig.get('base', 'username')
password = myconfig.get('base', 'password')
cc98_username = myconfig.get('cc98', 'username')
cc98_password = myconfig.get('cc98', 'password')

@app.route('/', methods=['GET'])
def index():
    res = {}

    sess = zju(
        username=username,
        password=password,
        cc98_username=cc98_username,
        cc98_password=cc98_password
    )

    try:
        t = sess.login()
        sess.go(res)
    except Exception:
        pass

    return render_template('index.html', variable=res)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
