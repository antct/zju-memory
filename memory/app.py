from flask import Flask, render_template, request, jsonify, make_response
from src.core import zju
from src.pool import pool
from src.myredis import myredis
from src.myconfig import myconfig

app = Flask(__name__, template_folder='html')

myredis = myredis(redis_type=0)
myconfig = myconfig()

cc98_username = myconfig.get('cc98', 'username')
cc98_password = myconfig.get('cc98', 'password')

@app.route('/qrcode', methods=['GET'])
def qrcode():
    res = {}
    try:
        res['code'] = 0
        res['msg'] = 'qrcode ok'
        res['src'], uuid = zju.get_qrcode()
        res['uuid'] = uuid
    except Exception:
        res['code'] = 1
        res['msg'] = 'qrcode fail'
    return make_response(jsonify(res), 200)

@app.route('/qrpoll', methods=['GET'])
def qrpoll():
    res = {}
    uuid = str(request.args.get('uuid'))
    try:
        token = zju.get_qrcode_token(uuid)
        res['code'] = 0
        res['msg'] = 'qrcode pass'
        res['token'] = token
    except Exception:
        res['code'] = 1
        res['msg'] = 'qrcode invalid'
    return make_response(jsonify(res), 200)

@app.route('/qrlogin', methods=['GET'])
def qrlogin():
    res = {}
    sess = zju(
        cc98_username=cc98_username,
        cc98_password=cc98_password
    )
    token = str(request.args.get('token'))

    try:
        sess.login_qrcode(token)
    except Exception:
        res['code'] = 1
        res['msg'] = 'login error'

    try:
        sess.go(res)
        res['code'] = 0
        res['msg'] = 'data ok'
    except Exception:
        res['code'] = 2
        res['msg'] = 'data error'
    finally:
        del sess

    return make_response(jsonify(res), 200)

@app.route('/login', methods=['POST'])
def login():
    res = {}
    username = request.form['username']
    password = request.form['password']

    sess = zju(
        username=username,
        password=password,
        cc98_username=cc98_username,
        cc98_password=cc98_password
    )

    try:
        t = sess.login()
        res['code'] = t['code']
        res['msg'] = t['msg']
    except Exception:
        res['code'] = 3
        res['msg'] = 'login error'
        del sess
        return make_response(jsonify(res), 200)

    if res['code'] != 0:
        del sess
        return make_response(jsonify(res), 200)

    try:
        sess.go(res)
        del sess
        return make_response(jsonify(res), 200)
    except Exception:
        res['code'] = 4
        res['msg'] = 'fetch error'
        del sess
        return make_response(jsonify(res), 200)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
