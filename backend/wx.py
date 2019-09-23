import os
import requests
import datetime
import random
import string
import hashlib
import time

class sign():
    def __init__(self):
        self._appid = ''
        self._secret = ''

        self._temp_path = './wx'
        if not os.path.exists(self._temp_path):
            os.mkdir(self._temp_path)

        self._temp_token = './wx/temp_token'
        self._temp_jsapi = './wx/temp_jsapi'
        if not os.path.exists(self._temp_token):
            self._temp_init()

    def _temp_init(self):
        with open(self._temp_token, "w+") as f:
            f.write(str({'token':'', 'time':'2019-01-01 00:00:00'}))
        with open(self._temp_jsapi, "w+") as f:
            f.write(str({'ticket':'', 'time':'2019-01-01 00:00:00'}))
    
    def _get_access_token(self):
        url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential'
        data = {
            'appid': self._appid,
            'secret': self._secret
        }
        res = requests.post(url=url, data=data).json()
        access_token = res['access_token']
        access_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        access_dict = {
            'token': access_token,
            'time': access_time
        }
        with open(self._temp_token, "w+") as wf:
            wf.write(str(access_dict))
        return access_token
    
    def _get_jsapi_ticket(self):
        jsapi_content = None
        with open(self._temp_jsapi, 'r') as f:
            jsapi_content = eval(f.read())
        
        old_ticket = jsapi_content['ticket']
        old_time = jsapi_content['time']

        old_time = datetime.datetime.strptime(old_time, "%Y-%m-%d %H:%M:%S")
        now_time = datetime.datetime.now()

        jsapi_ticket = None
        if old_time + datetime.timedelta(seconds=7200) >= now_time:
            jsapi_ticket = old_ticket
        else:
            token_content = None
            with open(self._temp_token, "r") as f:
                token_content = eval(f.read())
            
            old_token = token_content['token']
            old_time = token_content['time']

            old_time = datetime.datetime.strptime(old_time, "%Y-%m-%d %H:%M:%S")
            now_time = datetime.datetime.now()
            
            access_token = None

            if old_time + datetime.timedelta(seconds=7200) >= now_time:
                access_token = old_token
            else:
                access_token = self._get_access_token()

            res = requests.get('https://api.weixin.qq.com/cgi-bin/ticket/getticket?access_token={}&type=jsapi'.format(access_token)).json()
            
            jsapi_ticket = res['ticket']
            jsapi_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            jsapi_dict = {
                'ticket': jsapi_ticket,
                'time': jsapi_time
            }
            with open(self._temp_jsapi, "w+") as wf:
                wf.write(str(jsapi_dict))
        return jsapi_ticket

    def _get_random_nonceStr(self):
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(15))

    def _get_time_stamp(self):
        return int(time.time())

    def get_signature(self, url):
        ret = {
            'nonceStr': self._get_random_nonceStr(),
            'jsapi_ticket': self._get_jsapi_ticket(),
            'timestamp': self._get_time_stamp(),
            'url': url
        }
        string = '&'.join(['%s=%s' % (key.lower(), ret[key]) for key in sorted(ret)])
        ret['signature'] = hashlib.sha1(string.encode('utf-8')).hexdigest()
        ret['appid'] = self._appid
        return ret
