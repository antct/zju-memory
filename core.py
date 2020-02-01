import requests
import base64
import re
import bs4
import sys
import string
import datetime
import copy
import json
import os
import random
import threading
import multiprocessing
import queue
import traceback
# import gevent
from io import BytesIO
from myredis import myredis

myredis = myredis(redis_type=0)

class decorators():
    @staticmethod
    def retry(times, debug=True):
        def outer_wrapper(func):
            def inner_wrapper(self, *arg, **kwargs):
                for i in range(times):
                    try:
                        start_time = datetime.datetime.now()
                        ret = func(self, *arg, **kwargs)
                        end_time = datetime.datetime.now()
                        run_time = (end_time - start_time).seconds
                        if debug:
                            print("func: {:<15}\tuser: {:<10}\ttime: {}s".format(func.__name__, self._username, run_time))
                        return ret
                    except requests.exceptions.ReadTimeout:
                        # return code -2
                        if func.__name == 'login':
                            return {'code': -2, 'msg': 'timeout error'}
                        else:
                            func_key = func.__name__[func.__name__.rfind('_')+1:]
                            arg[0][func_key] = {'code': -2}
                        return
                    except Exception:
                        exc_type, exc_value, exc_tb = sys.exc_info()
                        exception_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb, limit=2))
                        print("func: {:<15}\tuser: {:<10}\te: \n\n{}".format(func.__name__, self._username, exception_text))
                        if i != times - 1:
                            continue
                        else:
                            if func.__name__ == 'login':
                                return {'code': -1, 'msg': 'undefined error'}
                            else:
                                func_key = func.__name__[func.__name__.rfind('_')+1:]
                                arg[0][func_key] = {'code': -1}
                            # raise e
            return inner_wrapper
        return outer_wrapper
        

class zju():
    def __init__(self, username=None, password=None, cc98_username=None, cc98_password=None):
        # normal login need username, qrcode dont't need
        if username is not None:
            self._username = username
            self._password = password
            self._stuid = self._username

            # 315: 5
            self._grade = int(self._stuid[2])

            # 315: 10-5=5
            # 316: 10-6=4
            self._semester_num = 10 - self._grade

        # wait login
        self._cert = None
        self._name = None
        self._createdate = None
        self._expdate = None
        self._dates = None
        self._account = None
        self._gender = None
        self._type = None
        self._expire = None

        # timeout setting
        self._timeout = 20

        # default headers
        self._headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Access-Control-Allow-Origin': '*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.119 Safari/537.36'
        }

        # default session
        self._session = None
        self._cookies = None

        # thread lock
        self._lock = threading.Lock()

        # ecard config
        self._query_start = '20170101'
        self._query_end = datetime.datetime.now().strftime("%Y%m%d")
        self._query_length = 800
        self._ecard_threads = 4

        # jwbinfosys config
        self._base_year = 2019

        # library config
        # 0 for zjuam login, 1 for normal login
        self._library_login_mode = 0
        self._library_threads = 2

        # cc98 config
        self._cc98_public_client_id = '9a1fd200-8687-44b1-4c20-08d50a96e5cd'
        self._cc98_public_client_secret = '8b53f727-08e2-4509-8857-e34bf92b27f2'
        self._cc98_username = cc98_username
        self._cc98_password = cc98_password

        # sport config
        # two different login way
        self._sport_login_mode = 0

    def _get(self, sess, *args, **kwargs):
        kwargs.update({'timeout': self._timeout})
        return sess.get(*args, **kwargs)

    def _post(self, sess, *args, **kwargs):
        kwargs.update({'timeout': self._timeout})
        return sess.post(*args, **kwargs)        

    @staticmethod
    def get_qrcode():
        import qrcode
        res = requests.get(url='https://zjuam.zju.edu.cn/cas/login')
        uuid = re.search('id="uuid" value="(.*?)"', res.text).group(1)
        qrcode_url = 'http://zjuam.zju.edu.cn:80/cas/qrcode/login?qrcode={}'.format(uuid)
        img = qrcode.make(qrcode_url)
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        byte_data = buffer.getvalue()
        base64_str = base64.b64encode(byte_data)
        return str(base64_str, encoding='utf-8'), str(uuid)

    @staticmethod
    def get_qrcode_token(uuid):
        polling_url = 'https://zjuam.zju.edu.cn/cas/qrcode/polling?uuid={}'.format(uuid)
        res = requests.get(url=polling_url, timeout=30).json()
        url = res['url']
        token = url[url.find('?')+7:]
        return token

    @decorators.retry(2)
    def login_qrcode(self, token):
        self._session = requests.Session()
        self._session.headers.update(self._headers)
        sess = self._session

        url = 'https://zjuam.zju.edu.cn/cas/login?token=' + token
        res = self._get(sess=sess, url=url)

        try:
            res = self._get(sess=sess, url='http://mapp.zju.edu.cn/lightapp/lightapp/getCardDetail').json()
            card = res['data']['query_card']['card'][0]
            self._username = card['sno']
            self._stuid = self._username
            self._grade = int(self._stuid[2])
            self._semester_num = 10 - self._grade

            self._cert = card['cert']
            self._name = card['name']
            self._account = card['account']
            self._createdate = card['createdate']
            self._expdate = card['expdate']

            format_now_date = datetime.datetime.now()
            str_now_date = format_now_date.strftime("%Y%m%d")
            format_create_date = datetime.datetime.strptime(self._createdate, "%Y%m%d")

            # actually, not accurate
            self._dates = (format_now_date - format_create_date).days
            self._expire = 1 if str_now_date > self._expdate else 0

            self._type = 'ugrs' if self._username[0] == '3' else 'grs'
            self._gender = 'boy' if int(self._cert[-2]) % 2 else 'girl'
        except Exception:
            self._name = 'null'
            self._dates = 'null'
            self._type = 'ugrs' if self._username[0] == '3' else 'grs'
            self._gender = 'boy'
            self._expire = 1

    def _authcode_crack(self, raw):
        from PIL import Image
        import tesserocr

        image = Image.open(raw)
        image = image.convert('L')
        threshold = 128
        table = [0 if i < threshold else 1 for i in range(256)]
        image = image.point(table, "1")

        result = tesserocr.image_to_text(image)
        result = result.strip().replace(' ', '')
        return result

    def _rsa_encrypt(self, password_str, e_str, M_str):
        password_bytes = bytes(password_str, 'ascii')
        password_int = int.from_bytes(password_bytes, 'big')
        e_int = int(e_str, 16)
        M_int = int(M_str, 16)
        result_int = pow(password_int, e_int, M_int)
        return hex(result_int)[2:].rjust(128, '0')

    @decorators.retry(2)
    def login(self):
        # need initialize
        self._session = requests.Session()
        self._session.headers.update(self._headers)
        sess = self._session

        res = self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/login')
        execution = re.search('name="execution" value="(.*?)"', res.text).group(1)
        # self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/v2/getKaptchaStatus')
        res = self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/v2/getPubKey').json()
        n, e = res['modulus'], res['exponent']
        encrypt_password = self._rsa_encrypt(self._password, e, n)

        data = {
            'username': self._username,
            'password': encrypt_password,
            'execution': execution,
            '_eventId': 'submit'
        }
        res = self._post(sess=sess, url='https://zjuam.zju.edu.cn/cas/login', data=data)
        
        ret = {}
        if not re.search('class="login-page"', res.text):
            if re.search('id="time-box"', res.text):
                ret['code'] = 2
                ret['msg'] = 'account lock'
            else:
                try:
                    res = self._get(sess=sess, url='http://mapp.zju.edu.cn/lightapp/lightapp/getCardDetail').json()
                    card = res['data']['query_card']['card'][0]
                    
                    self._cert = card['cert']
                    self._name = card['name']
                    self._account = card['account']
                    self._createdate = card['createdate']
                    self._expdate = card['expdate']

                    format_now_date = datetime.datetime.now()
                    str_now_date = format_now_date.strftime("%Y%m%d")
                    format_create_date = datetime.datetime.strptime(self._createdate, "%Y%m%d")

                    # actually, not accurate
                    self._dates = (format_now_date - format_create_date).days
                    self._expire = 1 if str_now_date > self._expdate else 0

                    self._type = 'ugrs' if self._username[0] == '3' else 'grs'
                    self._gender = 'boy' if int(self._cert[-2]) % 2 else 'girl'
                except Exception:
                    self._name = 'null'
                    self._dates = 'null'
                    self._type = 'ugrs' if self._username[0] == '3' else 'grs'
                    self._gender = 'boy'
                    self._expire = 1

                ret['code'] = 0
                ret['msg'] = 'login ok'
        else:
            # bug, fixed
            ret['code'] = 1
            ret['msg'] = 'wrong password'
        return ret

    def go(self, response):
        ugrs_tasks = [zju._get_ecard, zju._get_library, zju._get_jwbinfosys, zju._get_sport, zju._get_cc98]
        grs_tasks = [zju._get_ecard, zju._get_library, zju._get_grs, zju._get_cc98]

        tasks = ugrs_tasks if self._type == 'ugrs' else grs_tasks
        tasks = [threading.Thread(target=i, args=(self, response)) for i in tasks]

        try:
            start_time = datetime.datetime.now()
                        
            for task in tasks:
                task.start()
            for task in tasks:
                task.join()

            end_time = datetime.datetime.now()
            run_time = (end_time - start_time).seconds

            response['basic'] = {}
            response['basic']['gender'] = self._gender
            response['basic']['name'] = self._name
            response['basic']['date'] = self._dates
            response['basic']['type'] = self._type
            response['basic']['expire'] = self._expire

            ugrs_check_list = ['jwbinfosys', 'ecard', 'library', 'cc98', 'sport']
            grs_check_list = ['jwbinfosys', 'ecard', 'library', 'cc98']
            check_list = ugrs_check_list if self._type == 'ugrs' else grs_check_list
            missing_list = ['{}: miss'.format(i) if i not in response else '{}: {}'.format(i, response[i]['code']) for i in check_list]
        except Exception as e:
            raise e

    @decorators.retry(2)
    def _get_grs(self, response):
        # this part need change user-agent
        sess = copy.deepcopy(self._session)

        # get grs token
        self._lock.acquire()
        # not need
        # self._get(sess=sess, url='https://grs.zju.edu.cn/cas/login?service=http://grs.zju.edu.cn/allogene/page/home.htm')
        params = {
            'response_type': 'code',
            'client_id': 'yckFoYFlgWxnu7Bn1N',
            'redirect_uri': 'http://grs.zju.edu.cn/allogene/page/home.htm'
        }
        self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/oauth2.0/authorize', params=params)
        self._lock.release()

        # grs course table
        res = self._get(sess=sess, url='http://grs.zju.edu.cn/py/page/student/grkcgl.htm')
        soup = bs4.BeautifulSoup(res.text, 'html.parser')

        trs = []
        tables = soup.findAll(class_='xkmid')
        tables = [i.find('table') for i in tables]
        for table in tables:
            trs.extend(table.findAll('tr')[1:])

        grs = {}
        
        count, major_count, credit = 0, 0, 0
        first_course = {
            'name': '',
            'teacher': '',
            'place': '',
            'time': '9999999' # 2019春10
        }
        semester2num, course2score, teacher2num, teacher2course = {}, {}, {}, {}
        for tr in trs:
            tds = tr.findAll('td')

            # 未选 || 正在修读 || 已获得学分
            course_status = tds[-1].get('name')
            if course_status == '未选' or course_status == '待处理':
                continue

            try:
                course_type, course_name, course_property, course_credit = tds[0].text, tds[2].text, tds[3].text, tds[4].text
                course_year, course_semester, course_teacher, course_info = tds[5].text, tds[6].text, tds[7].text, tds[8].strings
                course_score = tds[-1].text
                course_info = [i for i in course_info]
                course_weekday = course_info[1]
                course_time = course_info[2]
                course_place = course_info[3]
            except Exception:
                continue

            course_semester_code = {'秋': 1, '秋冬': 1, '冬': 2, '春': 3, '春夏': 3, '夏': 4}
            course_format_time = '{}{}{}'.format(course_year, course_semester_code[course_semester], course_time.split('-')[0])

            if course_format_time < first_course['time']:
                first_course['name'] = course_name
                first_course['teacher'] = course_teacher
                first_course['place'] = course_place
                first_course['time'] = course_format_time

            # condition
            if course_status == '已获得学分':
                count += 1
                if course_property.find('专业') != -1:
                    major_count += 1

                if course_score.find('课程评价') != -1:
                    pass
                else:
                    # score may be 通过
                    try:
                        course_score = int(course_score.split('|')[1].strip())
                        course2score[course_name] = course_score
                    except Exception:
                        pass

            # several teacher
            if course_teacher not in teacher2num:
                teacher2num[course_teacher] = 1
            else:
                teacher2num[course_teacher] += 1

            if course_teacher not in teacher2course:
                teacher2course[course_teacher] = [course_name]
            else:
                teacher2course[course_teacher].append(course_name)

            if course_year+course_semester not in semester2num:
                semester2num[course_year+course_semester] = 1
            else:
                semester2num[course_year+course_semester] += 1
                
            credit += float(course_credit)
    
        grs['total_credit'] = credit
        grs['major_count'] = major_count
        grs['total_count'] = count
        course2score = sorted(course2score.items(), key=lambda d:d[1],reverse=True)
        # highest 4 courses
        grs['score'] = [{'name': i[0], 'count': i[1]} for i in course2score[:4]]
        
        grs['first_course'] = first_course

        # the teacher with most courses
        teacher2num = sorted(teacher2num.items(), key=lambda d:d[1],reverse=True)
        grs['teacher'] = {
            'name': teacher2num[0][0] if len(teacher2num) else 'null',
            'count': teacher2num[0][1] if len(teacher2num) else 'null',
            'course': teacher2course[teacher2num[0][0]] if len(teacher2num) else 'null',
            # 2019/06/22
            'total_count': len(teacher2num) if len(teacher2num) else 'null'
        }

        semesters = sorted(semester2num.keys())
        semester2num = sorted(semester2num.items(), key=lambda d:d[1],reverse=True)
        grs['semester'] = {
            'name': semester2num[0][0] if len(semester2num) else 'null',
            'count': semester2num[0][1] if len(semester2num) else 'null',
            'first': semesters[0] if len(semesters) else 'null',
            'last': semesters[-1] if len(semesters) else 'null',
            'avg': int(sum([i[1] for i in semester2num]) / len(semester2num)) if len(semester2num) else 'null'
        }
        grs['code'] = 0

        response['jwbinfosys'] = grs

    @decorators.retry(2)
    def _get_exp(self, response):
        sess = copy.deepcopy(self._session)

        # self._get(sess=sess, url='http://sygl.zju.edu.cn/')
        self._get(sess=sess, url='http://sygl.zju.edu.cn/sso')
        self._get(sess=sess, url='http://sygl.zju.edu.cn/st/exps')

    def _get_ecard_part(self, sess, start_page, end_page, q):
        # from gevent import monkey; monkey.patch_all()

        most_tranamt = {
            'occtime': '',
            'mercname': '',
            'tranamt': 0.0
        }
        day2tranamt, dining2count, merc2count = {}, {}, {}
        shower, market, normal, bank, alipay, web = 0, 0, 0, 0, 0, 0

        for i in range(start_page, end_page):
            params = {
                'curpage': '{}'.format(i),
                'pagesize': '50',
                'account': '{}'.format(self._account),
                'queryStart': self._query_start,
                'queryEnd': self._query_end
            }
            res = self._get(sess=sess, url='http://mapp.zju.edu.cn/lightapp/lightapp/getHistoryConsumption', params=params).json()
            items = res['data']['query_his_total']['total']
            for item in items:
                # 20190120105050
                occtime = item['occtime']
                
                tranamt = int(item['sign_tranamt']) / 100.0
                tranname = item['tranname'].replace('\r', '').replace('\n', '').strip()
                mercname = item['mercname'].replace('\r', '').replace('\n', '').strip()
                trancode = item['trancode'].replace('\r', '').replace('\n', '').strip()

                # biggest tranamt
                if tranamt < 0 and tranamt < most_tranamt['tranamt']:
                    most_tranamt['occtime'] = occtime
                    most_tranamt['mercname'] = mercname
                    most_tranamt['tranamt'] = tranamt
                
                if tranamt < 0:
                    daytime = occtime[:8]
                    if daytime not in day2tranamt.keys():
                        day2tranamt[daytime] = 0
                    day2tranamt[daytime] += -1 * tranamt

                # merc
                if mercname not in merc2count.keys():
                    merc2count[mercname] = 1
                else:
                    merc2count[mercname] += 1

                if trancode == '15':
                    if mercname.find('水控') != -1 or mercname.find('水电费') != -1:
                        shower += 1
                    elif mercname.find('超市') or mercname.find('商贸') != -1:
                        market += 1
                    elif mercname.find('出国成绩') != -1:
                        pass
                    else:
                        normal += 1
                        if mercname not in dining2count.keys():
                            dining2count[mercname] = 1
                        else:
                            dining2count[mercname] += 1
                    continue
                        
                # bank
                if trancode == '16':
                    bank += 1
                    continue

                # normal
                if trancode == '94':
                    if mercname.find('网上缴费') != -1:
                        web += 1
                    elif mercname.find('水控') != -1 or mercname.find('水电费') != -1:
                        shower += 1
                    else:
                        normal += 1
                        if mercname not in dining2count.keys():
                            dining2count[mercname] = 1
                        else:
                            dining2count[mercname] += 1
                    continue

                # alipay
                if trancode == '1A':
                    alipay += 1
                    continue

        t = {
            'most_tranamt': most_tranamt,
            'day2tranamt': day2tranamt,
            'dining2count': dining2count,
            'merc2count': merc2count,
            'shower': shower,
            'market': market,
            'normal': normal,
            'bank': bank,
            'alipay': alipay,
            'web': web
        }

        q.put(t)
            
    @decorators.retry(2)
    def _get_ecard(self, response):
        sess = copy.deepcopy(self._session)

        # query total pages
        params = {
            'curpage': '1',
            'pagesize': '50',
            'account': '{}'.format(self._account),
            'queryStart': self._query_start,
            'queryEnd': self._query_end
        }
        
        res = self._get(sess=sess, url='http://mapp.zju.edu.cn/lightapp/lightapp/getHistoryConsumption', params=params).json()
        # may be divided by zero
        pages = int(int(res['data']['query_his_total']['rowcount']) / int(res['data']['query_his_total']['pagesize'])) + 1
        
        # define data
        ecard = {}
        most_tranamt = {
            'occtime': '',
            'mercname': '',
            'tranamt': 0.0
        }
        day2tranamt, merc2count, dining2count = {}, {}, {}
        shower, market, normal, bank, alipay, web = 0, 0, 0, 0, 0, 0

        t = []
        q = queue.Queue()

        # 20, 1-20 20/3
        # 0, 6, 13, 20
        indexs = [int(pages/(self._ecard_threads/i)) if i else 0 for i in range(0, self._ecard_threads+1)]

        for i in range(self._ecard_threads):
            t.append(threading.Thread(target=zju._get_ecard_part, args=(self, sess, indexs[i]+1, indexs[i+1]+1, q)))

        try:
            for i in t:
                i.start()
            for i in t:
                i.join()
        except Exception as e:
            raise e

        while not q.empty():
            t = q.get()
            most_tranamt = t['most_tranamt'] if t['most_tranamt']['tranamt'] < most_tranamt['tranamt'] else most_tranamt
            day2tranamt.update(t['day2tranamt'])

            alipay += t['alipay']
            shower += t['shower']
            normal += t['normal']
            market += t['market']
            bank += t['bank']
            web += t['web']

            for key, value in t['merc2count'].items():
                if key not in merc2count.keys():
                    merc2count[key] = value
                else:
                    merc2count[key] += value
            for key, value in t['dining2count'].items():
                if key not in dining2count.keys():
                    dining2count[key] = value
                else:
                    dining2count[key] += value

        merc_list = sorted(merc2count.items(), key=lambda d:d[1], reverse=True)
        # may be 水控
        most_merc = [{'mercname': i[0], 'count': i[1]} for i in merc_list[:4] if i[0].find('水控') == -1][:3]

        dining_list = sorted(dining2count.items(), key=lambda d:d[1], reverse=True)
        most_dining = [{'mercname': i[0], 'count': i[1]} for i in dining_list[:2]]

        occtime = most_tranamt['occtime']
        most_tranamt['occtime'] = '{}-{}-{} {}:{}:{}'.format(occtime[0:4], occtime[4:6], occtime[6:8], occtime[8:10], occtime[10:12], occtime[12:14])
        most_tranamt['tranamt'] = -1 * most_tranamt['tranamt']

        try:
            day_span_list = sorted(day2tranamt.items(), key=lambda d:d[0])
            day_1, day_2 = day_span_list[0][0], datetime.datetime.now()
            day_span = (day_2 - datetime.datetime.strptime(day_1,"%Y%m%d")).days
        except Exception:
            day_span = "null"

        try:
            day_list = sorted(day2tranamt.items(), key=lambda d:d[1], reverse=True)
            most_day = {
                'occtime': '{}-{}-{}'.format(day_list[0][0][0:4], day_list[0][0][4:6], day_list[0][0][6:8]),
                'tranamt': day_list[0][1]
            }
        except Exception:
            most_day = {
                'occtime': 'null',
                'tranamt': 'null'
            }

        ecard['code'] = 0
        ecard['shower'] = shower
        ecard['web'] = web
        ecard['bank'] = bank
        ecard['normal'] = normal
        ecard['alipay'] = alipay
        ecard['market'] = market
        ecard['most_tranamt'] = most_tranamt
        ecard['most_dining'] = most_dining
        ecard['most_day'] = most_day
        ecard['most_merc'] = most_merc
        ecard['day_count'] = len(day_list)
        ecard['day_span'] = day_span
        ecard['merc_count'] = len(merc_list)
        response['ecard'] = ecard

    def _get_jwbinfosys_util(self, res, teacher2num, semester2num, teacher2course, slug):
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        year = soup.find(id='xnd').find(attrs={'selected': "selected"}).text
        table = soup.find(id='xsgrid')
        trs = table.findAll('tr')[1:]
        for tr in trs:
            tds = tr.findAll('td')
            course_id, course_name, teacher, semester = tds[0].text, tds[1].text, tds[2].text, tds[3].text
            teachers = teacher.split('<br/>')
            for teacher in teachers:
                if teacher not in teacher2course.keys():
                    teacher2course[teacher] = [course_name]
                else:
                    teacher2course[teacher].append(course_name)
                
                if teacher not in teacher2num.keys():
                    teacher2num[teacher] = 1
                else:
                    teacher2num[teacher] += 1
        # 2015-2016 13s
        semester2num[slug] = len(trs)

    def _get_jwbinfosys_course(self, sess):

        teacher2num = {}
        semester2num = {}
        teacher2course = {}

        res = None
        res = self._get(sess=sess, url='http://jwbinfosys.zju.edu.cn/xskbcx.aspx?xh={}'.format(self._stuid))
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        # year count in course table
        semester_num = len(soup.find(id='xnd').findAll('option'))

        # four-year system
        # 2015: 5-4=1 2019-1=2018 right
        # 2016: 4-4=0 2019-0=2019 right
        # five-year system
        # 2014: 6-5=1 2019-1=2018 right
        # 2015: 5-5=1 2019-0=2019 right
        semester_diff = self._semester_num - semester_num
        base = self._base_year - semester_diff
        
        # 秋冬 or 春夏
        default_semester = soup.find(id='xqd').find(attrs={'selected': "selected"}).text
        left_semester = default_semester
        right_semester = '春、夏' if left_semester == '秋、冬' else '秋、冬'
        

        self._get_jwbinfosys_util(res, teacher2num, semester2num, teacher2course, '{}-{} {}'.format(base, base+1, left_semester.replace('、', '')))
        # viewstate = re.search('name="__VIEWSTATE" value=".*?"', res.text).group(0)[26:-1]
        viewstate = re.search('name="__VIEWSTATE" value="(.*?)"', res.text).group(1)
        data = {
                '__VIEWSTATE': viewstate,
                '__EVENTTARGET': 'xqd',
            }
        if left_semester == '秋、冬':
            data['xqd'] = '2|春、夏'.encode('GBK')
        if left_semester == '春、夏':
            data['xqd'] = '1|秋、冬'.encode('GBK')
        res = self._post(sess=sess, url='http://jwbinfosys.zju.edu.cn/xskbcx.aspx?xh={}'.format(self._stuid), data=data)
        self._get_jwbinfosys_util(res, teacher2num, semester2num, teacher2course, '{}-{} {}'.format(base, base+1, right_semester.replace('、', '')))

        for i in range(1, semester_num):
            # xnd, change year
            viewstate = re.search('name="__VIEWSTATE" value="(.*?)"', res.text).group(1)
            data = {
                '__EVENTTARGET': 'xnd',
                '__VIEWSTATE': viewstate,
                'xnd': '{}-{}'.format(base-i, base-i+1),
            }
            res = self._post(sess=sess, url='http://jwbinfosys.zju.edu.cn/xskbcx.aspx?xh={}'.format(self._stuid), data=data)
            self._get_jwbinfosys_util(res, teacher2num, semester2num, teacher2course, '{}-{} {}'.format(base-i, base-i+1, left_semester.replace('、', '')))

            # xqd, change semester
            viewstate = re.search('name="__VIEWSTATE" value="(.*?)"', res.text).group(1)

            copy_res = res

            data = {
                '__VIEWSTATE': viewstate,
                '__EVENTTARGET': 'xqd',
            }
            if left_semester == '秋、冬':
                data['xqd'] = '2|春、夏'.encode('GBK')
            if left_semester == '春、夏':
                data['xqd'] = '1|秋、冬'.encode('GBK')
            res = self._post(sess=sess, url='http://jwbinfosys.zju.edu.cn/xskbcx.aspx?xh={}'.format(self._stuid), data=data)
            self._get_jwbinfosys_util(res, teacher2num, semester2num, teacher2course, '{}-{} {}'.format(base-i, base-i+1, right_semester.replace('、', '')))

            # first semester is always 秋冬
            if left_semester == '秋、冬':
                res = copy_res

        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        year = soup.find(id='xnd').find(attrs={'selected': "selected"}).text
        table = soup.find(id='xsgrid')
        trs = table.findAll('tr')[1:]

        first_semester_course = []

        # default monday
        for tr in trs:
            tds = tr.findAll('td')
            course_name, teacher, semester, time, place = tds[1].text, tds[2].text, tds[3].text, tds[4].text, tds[5].text
            if semester.find('秋') != -1:
                places = place.split('<br/>')
                times = time.split('<br/>')
                time, place = None, None
                if len(times) >= 2: 
                    time = sorted(times)[0]
                    place = places[times.index(time)]
                else:
                    place = places[0]
                    time = times[0]
                first_semester_course.append((course_name, teacher, place, time))
        first_semester_course = sorted(first_semester_course, key=lambda d:d[-1])
        first_course = None

        if first_semester_course[0][0] == '军训':
            first_course = {
                'name': first_semester_course[1][0],
                'teacher': first_semester_course[1][1],
                'place': first_semester_course[1][2]
            }
        else:
            first_course = {
                'name': first_semester_course[0][0],
                'teacher': first_semester_course[0][1],
                'place': first_semester_course[0][2]
            }

        return teacher2num, teacher2course, semester2num, first_course

    @decorators.retry(2)
    def _get_jwbinfosys(self, response):
        # ajax
        # get base cookie
        sess = copy.deepcopy(self._session)

        jwbinfosys = {}

        # prefetch
        res = self._get(sess=sess, url='http://jwbinfosys.zju.edu.cn/default2.aspx')
        if res.text.find('学籍状态') != -1:
            jwbinfosys['code'] = 1
            response['jwbinfosys'] = jwbinfosys
            return
        if res.text.find('教学质量进行客观评价') != -1:
            jwbinfosys['code'] = 2
            response['jwbinfosys'] = jwbinfosys
            return

        # major grade
        res = self._get(sess=sess, url='http://jwbinfosys.zju.edu.cn/xscj_zg.aspx?xh={}'.format(self._stuid))
        tds = re.findall('<tr[\S\s]*?</tr>', res.text)[1:]
        jwbinfosys['major_count'] = len(tds)

        # all grade
        res = self._get(sess=sess, url='http://jwbinfosys.zju.edu.cn/xscj.aspx?xh={}'.format(self._stuid))
        # constant
        viewstate = re.search('name="__VIEWSTATE" value="(.*?)"', res.text).group(1)
        data = {
            '__VIEWSTATE': viewstate,
            'Button2': '在校成绩查询'.encode('GBK')
        }

        res = self._post(sess=sess, url='http://jwbinfosys.zju.edu.cn/xscj.aspx?xh={}'.format(self._stuid), data=data)
        tds = re.findall('<tr[\S\s]*?</tr>', res.text)[1:]
        
        # course_name: score
        course2score = {}
        total_credit = 0
        # sport_name: count
        sport2num = {}

        for td in tds:
            infos = re.findall('<td>[\S\s]*?</td>', td)
            infos = [i.replace('<td>', '').replace('</td>', '') for i in infos]
            course_info, course_name, score, credit, gp = infos[:5]
            # yet not pass, todo
            try:
                total_credit += float(credit)
            except Exception:
                continue

            course_time = course_info[1:12]
            course_id = course_info[14:22]

            # sport course
            if course_id[:3] == '401':
                index = course_name.find('（')
                course_type = course_name if index == -1 else course_name[:index]
                if course_type not in sport2num.keys():
                    sport2num[course_type] = 1
                else:
                    sport2num[course_type] += 1

            # score may be '合格'
            try:
                if score.isdigit():
                    course2score[course_name] = int(score)
                    continue
                score2gp = {'A+': '5.0', 'A': '4.5', 'A-': '4.2', \
                    'B+': '3.8', 'B': '3.5', 'B-': '3.2', \
                        'C+': '2.8', 'C': '2.5', 'C-': '2.2', \
                            'D': '1.5', 'F': '0'}
                if score in score2gp:
                    gp = score2gp[score]
                course2score[course_name] = 95-10*(5-float(gp))
            except Exception as e:
                print(score)
                print(e)
                continue

        jwbinfosys['sport_count'] = len(sport2num)
        jwbinfosys['total_credit'] = total_credit
        jwbinfosys['total_count'] = len(tds)
        course2score = sorted(course2score.items(), key=lambda d:d[1],reverse=True)
        # highest 4 courses
        jwbinfosys['score'] = [{'name': i[0], 'count': i[1]} for i in course2score[:4]]

        # course info
        try:
            teacher2num, teacher2course, semester2num, first_course = self._get_jwbinfosys_course(sess=sess)
        except Exception:
            response['jwbinfosys'] = jwbinfosys
            return
        
        jwbinfosys['first_course'] = first_course

        # the teacher with most courses
        teacher2num = sorted(teacher2num.items(), key=lambda d:d[1],reverse=True)
        jwbinfosys['teacher'] = {
            'name': teacher2num[0][0],
            'count': teacher2num[0][1],
            'course': teacher2course[teacher2num[0][0]],
            # 2019/06/22
            'total_count': len(teacher2num)
        }

        semesters = sorted(semester2num.keys())
        semester2num = sorted(semester2num.items(), key=lambda d:d[1],reverse=True)
        jwbinfosys['semester'] = {
            'name': semester2num[0][0],
            'count': semester2num[0][1],
            'first': semesters[0],
            'last': semesters[-1],
            'avg': int(sum([i[1] for i in semester2num]) / len(semester2num))
        }
        jwbinfosys['code'] = 0

        response['jwbinfosys'] = jwbinfosys

    def _get_library_util(self, date):
        date1 = datetime.datetime.strptime(date, '%Y%m%d')
        delta = datetime.timedelta(days=-40)
        date2 = date1 + delta
        return date2.strftime('%Y-%m-%d')

    def _get_library_topic(self, sess, start, end, topic_urls, q):
        topic2num = {}
        idx2page = {}
        for i in range(start, end):
            topic_url = topic_urls[i]
            res = self._get(sess=sess, url=topic_url)
            res.encoding = 'utf-8'
            soup = bs4.BeautifulSoup(res.text, 'html.parser')
            try:
                table = soup.findAll('table')[-2]
                trs = table.findAll('tr')[1:]
                for tr in trs:
                    tds = tr.findAll('td')
                    if tds[0].text.find('主题') != -1:
                        try:
                            for topic in ("".join(tds[1].text.strip('\n').split())).split('-'):
                                if topic not in topic2num.keys():
                                    topic2num[topic] = 1
                                else:
                                    topic2num[topic] += 1
                        except Exception:
                            pass
                    if tds[0].text.find('载体形态') != -1:
                        t = re.search('([0-9]*)页', tds[1].text)
                        if t is not None:
                            idx2page[i] = int(t.group(1))
                        else:
                            pass
            except Exception:
                pass
        q.put((topic2num, idx2page))

    @decorators.retry(2)
    def _get_library(self, response):
        # ISO-8859-1

        # need catch exception
        sess = copy.deepcopy(self._session)
        
        # zjuam login
        if self._library_login_mode == 0:
            res = self._get(sess=sess, url='http://webpac.zju.edu.cn/zjusso')
            res.encode = 'utf-8'
        # normal login
        else:
            sess_id = round(random.random() * 1000000000, 0)
            res = self._get(sess=sess, url='http://opac.zju.edu.cn/F?RN={}'.format(sess_id))
            res.encoding = 'utf-8'
            search_result = re.search('<a href="(.*?)".*?>我的图书馆</a>', res.text)
            library_url = search_result.group(1)

            code = self._get(sess=sess, url='http://opac.zju.edu.cn/cgi-bin/aleph_token.cgi', stream=True)
            crack_code = self._authcode_crack(code.raw)
            
            # print(crack_code)
            data = {
                'func': 'login-session',
                'login_source': 'bor-info',
                'bor_id': self._stuid,
                'bor_verification': self._cert[-6:],
                'bor_verification_2': crack_code,
                'bor_library': 'ZJU50'
            }

            # crack_code may be wrong
            res = self._post(sess=sess, url=library_url, data=data)

            res = self._get(sess=sess, url=library_url)
            res.encoding = 'utf-8'

        library = {}

        a = re.search('<a href=.*?func=bor-history-loan.*?</a>', res.text)
        if a is None:
            # 403
            library['code'] = 2
            response['library'] = library
            return
        else:
            a = a.group(0)

        href = re.search("\('(.*?)'\)", a).group(1)
        res = self._get(sess=sess, url=href)
        res.encoding = 'utf-8'
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        table = soup.findAll('table')[-1]
        trs = table.findAll('tr')[1:]

        book_info = []
        topic_urls = []
        author2num, place2num, topic2num, idx2page = {}, {}, {}, {}
        early_book = {
            'author': '',
            'name': '',
            'year': '9999'
        }
        long_book = {
            'author': '',
            'name': '',
            'day': 0,
        }

        try:
            for tr in trs:
                tds = tr.findAll('td')
                author = tds[1].text.strip(',').strip('，')
                book_name, year, date, return_date, place = tds[2].text, tds[3].text, tds[4].text, tds[6].text, tds[-1].text
                book_info.append((author, book_name, date))

                borrow_date = datetime.datetime.strptime(date, '%Y%m%d')
                return_date = datetime.datetime.strptime(return_date, '%Y%m%d')
                borrow_day = (return_date - borrow_date).days + 40

                if borrow_day > long_book['day']:
                    long_book['author'] = author
                    long_book['name'] = book_name
                    long_book['day'] = borrow_day

                if year < early_book['year']:
                    early_book['author'] = author
                    early_book['name']= book_name
                    early_book['year'] = year

                if place not in place2num.keys():
                    place2num[place] = 1
                else:
                    place2num[place] += 1

                if author not in author2num.keys():
                    author2num[author] = 1
                else:
                    author2num[author] += 1

                # topic
                topic_url = tds[2].find('a')['href']
                topic_urls.append(topic_url)
                    
            first_book = {
                'author': book_info[-1][0],
                'name': book_info[-1][1],
                'date': self._get_library_util(book_info[-1][2])
            }

            last_book = {
                'author': book_info[0][0],
                'name': book_info[0][1],
                'date': self._get_library_util(book_info[0][2])
            }

        except Exception as e:
            library['code'] = 1
            response['library'] = library
            return
        
        t = []
        q = queue.Queue()
        
        # 21 4: 0, 5, 10, 16, 21

        items = len(topic_urls)
        indexs = [int(items/(self._library_threads/i)) if i else 0 for i in range(0, self._library_threads+1)]
        
        for i in range(self._library_threads):
            t.append(threading.Thread(target=zju._get_library_topic, args=(self, sess, indexs[i], indexs[i+1], topic_urls, q)))
        try:
            for i in t:
                i.start()
            for i in t:
                i.join()
        except Exception as e:
            raise e

        while not q.empty():
            topic2num_t, idx2page_t =  q.get()
            idx2page.update(idx2page_t)
            for key, value in topic2num_t.items():
                if key not in topic2num.keys():
                    topic2num[key] = value
                else:
                    topic2num[key] += value

        topic2num = sorted(topic2num.items(), key=lambda d:d[1], reverse=True)
        place2num = sorted(place2num.items(), key=lambda d:d[1], reverse=True)
        author2num = sorted(author2num.items(), key=lambda d:d[1], reverse=True)
        idx2page = sorted(idx2page.items(), key=lambda d: d[1], reverse=True)

        library['code'] = 0
        library['count'] = len(book_info)
        library['most_author'] = {
            'name': author2num[0][0],
            'count': author2num[0][1]
        }
        library['long_book'] = long_book
        library['first_book'] = first_book
        library['last_book'] = last_book
        library['early_book'] = early_book
        library['most_place'] = {
            'count': len(place2num),
            'name': place2num[0][0]
        }
        # here may be error
        library['topic'] = {
            'count': len(topic2num),
            'label': [i[0] for i in topic2num[:6]]
        } 
        library['most_page'] = {
            'name': book_info[idx2page[0][0]][1] if len(idx2page) else 'null',
            'author': book_info[idx2page[0][0]][0] if len(idx2page) else 'null',
            'page': idx2page[0][1] if len(idx2page) else 'null'
        }
        response['library'] = library

    def _get_cc98_token(self):
        # already exists
        if myredis.getex('memory_token') != None:
            return
        # no token, but refresh_token exists
        # however, refresh_token not work properly

        data = {
            'client_id': self._cc98_public_client_id,
            'client_secret': self._cc98_public_client_secret,
            'grant_type': 'password',
            'username': self._cc98_username,
            'password': self._cc98_password,
        }
        res = requests.post(url='https://openid.cc98.org/connect/token', data=data, headers=self._headers).json()

        myredis.setex('memory_token', res['access_token'], res['expires_in'])
        myredis.setex('memory_token_type', res['token_type'], res['expires_in'])
        # here, refresh_token: 30 days, access_token: 1 hour
        myredis.setex('memory_refresh_token', res['refresh_token'], 24 * 30 * res['expires_in'])

    def _get_cc98_user(self, sess, title):
        follow_count, fan_count, like_count, pop_count = [0] * 4

        # username
        name = title.text.strip().strip('\n').strip()
        res = self._get(sess=sess, url="https://api-v2.cc98.org/user/name/{}".format(name)).json()

        cc98_id = res['id']
        follow_count = int(res['followCount'])
        fan_count = int(res['fanCount'])
        like_count = int(res['receivedLikeCount'])
        pop_count = int(res['popularity'])

        recent_topics, recent_topics_board = {}, {}

        start = 0
        while True:
            try:
                res = self._get(sess=sess, url="https://api.cc98.org/user/{}/recent-topic?from={}&size=20".format(cc98_id, 20*start)).json()
                if not len(res):
                    break
                for i in res:
                    time, board, title = i['time'], i['boardName'], i['title']
                    recent_topics[time] = title
                    if board not in recent_topics_board.keys():
                        recent_topics_board[board] = 1
                    else:
                        recent_topics_board[board] += 1
                if len(res) < 20:
                    break
            except Exception:
                break
            start += 1
    
        return name, follow_count, fan_count, like_count, pop_count, recent_topics, recent_topics_board

    @decorators.retry(2)
    def _get_cc98(self, response):
        sess = copy.deepcopy(self._session)

        # this api can't afford too much links
        self._lock.acquire()
        # self._get(sess=sess, url='https://account.cc98.org/signin-zjuinfo')
        res = self._get(sess=sess, url='https://account.cc98.org/My')
        self._lock.release()

        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        tables = soup.findAll(attrs={'class': "table table-sm"})
        titles = soup.findAll(attrs={'class': "card-title"})

        cc98 = {}
        cc98['count'] = len(tables)

        # if no cc98 account
        if len(tables) == 0:
            cc98['code'] = 2
            response['cc98'] = cc98
            return

        cc98['login_times'] = 0
        cc98['comment_times'] = 0
        cc98['register_time'] = '9999-99-99 99:99'

        # now, only the big account
        index, big_index = 0, 0
        for table in tables:
            trs = table.findAll('tr')
            info = [tr.findAll('td')[1].get_text() for tr in trs]
            register_time, last_login, login_times, comment_times = info[0], info[1], info[2], info[3]

            # big index, more comments more big
            if int(comment_times) > cc98['comment_times']:
                cc98['login_times'] = int(login_times)
                cc98['comment_times'] = int(comment_times)
                big_index = index

            # why need get register time here, big account != early account
            # 2020/1/11 0:09
            register_part1, register_part2 = register_time.split(' ')
            register_year, register_month, register_day = [int(i) for i in register_part1.split('/')]
            register_hour, register_minute = [int(i) for i in register_part2.split(':')]
            format_register_time = '{:02d}-{:02d}-{:02d} {:02d}:{:02d}'.format(register_year, register_month, register_day, register_hour, register_minute)

            if format_register_time < cc98['register_time']:
                cc98['register_time'] = format_register_time

            index += 1

        # need token
        self._get_cc98_token()
        sess.headers.update({'authorization': '%s %s' % (myredis.getex('memory_token_type'), myredis.getex('memory_token'))})

        name, follow_count, fan_count, like_count, pop_count, recent_topics, recent_topics_board = self._get_cc98_user(sess, titles[big_index])

        # write cc98 user info
        cc98['name'] = name
        cc98['post_count'] = len(list(recent_topics))
        cc98['follow_count'] = follow_count
        cc98['fan_count'] = fan_count
        cc98['like_count'] = like_count
        cc98['pop_count'] = pop_count

        # no post
        if not len(list(recent_topics)):
            cc98['code'] = 1
            response['cc98'] = cc98
            return
        
        recent_topics_list = sorted(recent_topics.items(), key=lambda d:d[0], reverse=False)
        trans_topic = [{'time': i[0][:10], 'title': i[1]} for i in recent_topics_list]
        first_topic = trans_topic[0]
        last_topic = trans_topic[-1]

        recent_topics_board_list = sorted(recent_topics_board.items(), key=lambda d:d[1], reverse=True)
        post_most_board = [{'board': i[0], 'count': i[1]} for i in recent_topics_board_list[:1]][0]

        cc98['code'] = 0
        cc98['topic_count'] = len(recent_topics_list)
        cc98['register_time'] = cc98['register_time'][:10]
        cc98['first_topic'] = first_topic
        cc98['last_topic'] = last_topic
        cc98['post_most'] = post_most_board

        response['cc98'] =  cc98

    @decorators.retry(2)
    def _get_sport(self, response):
        sess = copy.deepcopy(self._session)

        years, heights, weights, bmis, scores, runs = [], [], [], [], [], []
        vitals, shorts, jumps, stretchs, optionals = [], [], [], [], []


        if self._sport_login_mode == 1:
            chars = string.ascii_letters + string.digits
            open_id = "".join(random.sample(chars, 32))
            login_url = 'http://www.tyys.zju.edu.cn/weixin/wx_login.php?open_id={}'.format(open_id)
            res = self._get(sess=sess, url=login_url)
            data = {
                'username': self._username,
                'password': self._password,
                'postflag': 1,
                'mode': 2,
                'wx_login': 1
            }
            res = self._post(sess=sess, url=login_url, data=data)
            height_extract = lambda x: x.strip().strip('cm').strip()
            weight_extract = lambda x: x.strip().strip('kg').strip()
            normal_extract = lambda x: (x.strip().split('/')[0].strip(), int(x.strip().split('/')[1].strip()))
            process_run = lambda x: x.replace('.', "'").replace('"', "'")[-4:None]
            for year in range(2014, self._base_year+1):
                query_url = 'http://www.tyys.zju.edu.cn/weixin/wx_cjcx.php?open_id={}&type=2&ckxn={}'.format(open_id, year)
                res = self._get(sess=sess, url=query_url)
                res.encoding = 'utf-8'
                rows = bs4.BeautifulSoup(res.text, 'html.parser').find_all(class_='mui-row')
                cols = [row.find_all('div')[1].get_text() for row in rows ]
                if cols[-1].strip() in ['免测', '暂无', '缓测']:
                    continue
                try:
                    score = float(cols[-1].strip())
                    height, weight, bmi = height_extract(cols[0]), weight_extract(cols[1]), normal_extract(cols[2])[0]
                    vital, short, jump = normal_extract(cols[3])[1], normal_extract(cols[4])[1], normal_extract(cols[5])[1]
                    stretch, run, optional = normal_extract(cols[6])[1], process_run(normal_extract(cols[7])[0]), normal_extract(cols[8])[1]
                except Exception:
                    continue

                scores.append(score)
                years.append("{}-{}".format(year, year+1))
                heights.append(height), weights.append(weight), bmis.append(bmi)
                vitals.append(vital), shorts.append(short), jumps.append(jump)
                stretchs.append(stretch), runs.append(run), optionals.append(optional)
        else:
            res = self._get(sess=sess, url='http://www.tyys.zju.edu.cn/ggtypt')
            res = self._get(sess=sess, url='http://www.tyys.zju.edu.cn/pft/loginto')
            res = self._get(sess=sess, url='http://www.tyys.zju.edu.cn/pft/myresult')
            trs = bs4.BeautifulSoup(res.text, 'html.parser').find(id='dataTables-main').find('tbody').findAll('tr')

            for tr in trs[::-1]:
                tds = [i.get_text().strip() for i in tr.findAll('td')]
                if tds[-1] in ['免测', '暂无', '缓测']:
                    continue
                else:
                    score = float(tds[-1])

                try:
                    year, bmi, height, weight, run = tds[0], tds[2], tds[3], tds[4], tds[9].split('/')[0].replace('.', "'")
                    f = lambda x: int(x.split('/')[1])
                    vital, short, jump, stretch, optional = f(tds[5]), f(tds[6]), f(tds[7]), f(tds[8]), f(tds[10])
                except Exception:
                    continue

                # format: 2018-2019学年
                year = '{}-{}'.format(year[2:4], year[7:9])

                years.append(year), heights.append(height), weights.append(weight), scores.append(score), bmis.append(bmi)
                vitals.append(vital), shorts.append(short), jumps.append(jump), stretchs.append(stretch), optionals.append(optional)
                runs.append(run[-4: None].replace('"', "'"))

        try:
            avg = lambda x: sum(x) / len(x) if len(x) > 0 else 0
            avg_grades = {'vital': avg(vitals), 'short': avg(shorts), 'jump': avg(jumps), 'stretch': avg(stretchs), 'optional': avg(optionals)}
            item2name = {
                'vital': '肺活量', 'short': '50米跑', 'jump': '立定跳远', 'stretch': '坐位体前屈', \
                'optional': '引体向上' if self._gender == 'boy' else '仰卧起坐'
            }
            grades_list = sorted(avg_grades.items(), key=lambda x: x[1])
        except Exception:
            # len(x) == 0
            grades_list = [('null', 'null')]

        sport = {}
        sport['code'] = 0

        best = {'name': item2name[grades_list[-1][0]],'score': grades_list[-1][1]}
        worst = {'name': item2name[grades_list[0][0]],'score': grades_list[0][1]}

        sport['best'] = best
        sport['worst'] = worst
        sport['year'] = years
        sport['height'] = heights
        sport['weight'] = weights
        sport['bmi'] = bmis
        try:
            sport['score'] = max(scores)
        except Exception:
            sport['score'] = "null"
        try:
            sport['run'] = sorted(runs)[0]
        except Exception:
            sport['run'] = "null"
        response['sport'] =  sport
