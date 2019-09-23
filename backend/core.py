import requests
import base64
import re
import bs4
import sys
import datetime
import copy
import json
import qrcode
import os
import threading
import queue
# import gevent
import multiprocessing

from io import BytesIO
from logger import logger
from redis import redis

myredis = redis()
base_path = os.path.dirname(__file__)

class zju():
    def __init__(self, username=None, password=None):
        if username:
            self._username = username
            self._password = password
            self._stuid = self._username

            # 315: 5
            self._grade = int(self._stuid[2])
            
            # 315: 10-5=5
            # 316: 10-6=4
            self._semester_num = 10 - self._grade

        # wait login
        self._phone = None
        self._cert = None
        self._name = None
        self._account = None
        self._gender = None

        self._cc98_config = {}
        with open('{}/cc98.config'.format(base_path), 'r', encoding='utf-8') as f:
            self._cc98_config = eval(f.read())
        
        # timeout setting
        self._timeout = 5
        self._headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Access-Control-Allow-Origin': '*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.119 Safari/537.36'
        }
        self._session = requests.Session()
        self._cookies = None

        # ecard config
        self._query_start = '20150820'
        self._query_end = '20190915'
        self._ecard_threads = 2

        # jwbinfosys config
        self._base_year = 2019

        # library config
        self._library_threads = 4

    def _get(self, sess, *args, **kwargs):
        kwargs.update({'timeout': self._timeout})
        return sess.get(*args, **kwargs)

    def _post(self, sess, *args, **kwargs):
        kwargs.update({'timeout': self._timeout})
        return sess.post(*args, **kwargs)

    def get_qrcode(self):
        sess = self._session
        res = self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/login', headers=self._headers)
        uuid = re.search('id="uuid" value=".*?"', res.text).group(0)[17:-1]
        res = self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/v2/getPubKey', headers=self._headers).json()
        qrcode_url = 'http://zjuam.zju.edu.cn:80/cas/qrcode/login?qrcode={}'.format(uuid)
        
        img = qrcode.make(qrcode_url)

        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        byte_data = buffer.getvalue()
        base64_str = base64.b64encode(byte_data)
        return str(base64_str, encoding='utf-8'), str(uuid)

    def get_qrcode_token(self, uuid):
        sess = self._session
        polling_url = 'https://zjuam.zju.edu.cn/cas/qrcode/polling?uuid={}'.format(uuid)
        res = sess.get(url=polling_url, timeout=30).json()
        url = res['url']
        token = url[url.find('?')+7:]
        return token

    def login_qrcode(self, token):
        sess = self._session
        url = 'https://zjuam.zju.edu.cn/cas/login?token=' + token
        res = self._get(sess=sess, url=url)
        res = self._get(sess=sess, url='http://mapp.zju.edu.cn/lightapp/lightapp/getCardDetail').json()
        card = res['data']['query_card']['card'][0]
        self._username = card['sno']
        self._stuid = self._username
        self._grade = int(self._stuid[2])
        self._semester_num = 9 - self._grade
        self._phone = card['phone']
        self._cert = card['cert']
        self._name = card['name']
        self._account = card['account']
        self._gender = 'boy' if int(self._cert[-2]) % 2 else 'girl'

    def _rsa_encrypt(self, password_str, e_str, M_str):
        password_bytes = bytes(password_str, 'ascii') # I guess no other characters in password
        password_int = int.from_bytes(password_bytes,'big') # big endian bytes->int
        e_int = int(e_str, 16) # equal to 0x10001
        M_int = int(M_str, 16) # Modulus number
        result_int = pow(password_int, e_int, M_int) # pow is a built-in function in python
        return hex(result_int)[2:] # int->hex str

    def login(self):
        # from rsa import encrypt
        sess = self._session
        res = self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/v2/getPubKey', headers=self._headers).json()
        n, e = res['modulus'], res['exponent']
        encrypt_password = self._rsa_encrypt(self._password, e, n)
        res = self._get(sess=sess, url='https://zjuam.zju.edu.cn/cas/login?service=https://zuinfo.zju.edu.cn/system/login/login.zf')
        execution = re.search('name="execution" value=".*?"', res.text).group(0)[24:-1]
        data = {
            'username': self._username,
            'password': encrypt_password,
            'execution': execution,
            '_eventId': 'submit'
        }
        res = self._post(sess=sess, url='https://zjuam.zju.edu.cn/cas/login', data=data)
        status = re.search('class="login-page"', res.text)

        res = self._get(sess=sess, url='http://mapp.zju.edu.cn/lightapp/lightapp/getCardDetail').json()
        card = res['data']['query_card']['card'][0]
        self._phone = card['phone']
        self._cert = card['cert']
        self._name = card['name']
        self._account = card['account']
        self._gender = 'boy' if int(self._cert[-2]) % 2 else 'girl'
        return not status

    def go(self, res):
        t = []
        t.append(threading.Thread(target=zju._get_ecard,args=(self, res)))
        t.append(threading.Thread(target=zju._get_jwbinfosys,args=(self, res)))
        t.append(threading.Thread(target=zju._get_library,args=(self, res)))
        t.append(threading.Thread(target=zju._get_cc98,args=(self, res)))
        t.append(threading.Thread(target=zju._get_sport,args=(self, res)))
        try:
            for i in t:
                i.start()
            for i in t:
                i.join()
        except Exception as e:
            raise e

    def retry(times):
        def outer_wrapper(func):
            def inner_wrapper(self, *arg, **kwargs):
                for _ in range(times):
                    try:
                        starttime = datetime.datetime.now()
                        func(self, *arg, **kwargs)
                        endtime = datetime.datetime.now()
                        logger.info("func: {} time: {}s user: {}".format(func.__name__, (endtime - starttime).seconds, self._username))
                        #if no error, just break
                        break
                    except Exception as e:
                        logger.info("func: {} user: {} e: {}".format(func.__name__, self._username, e))
                        continue
            return inner_wrapper
        return outer_wrapper

    def _get_ecard_part(self, sess, start_page, end_page, q):
        # from gevent import monkey; monkey.patch_all()

        ecard_biggest = {
            'occtime': '',
            'mercname': '',
            'tranamt': 0.0
        }
        ecard_day, ecard_dining, ecard_merc = {}, {}, {}
        ecard_occtime = []
        ecard_shower, ecard_market, ecard_normal, ecard_bank, ecard_alipay, ecard_web = 0, 0, 0, 0, 0, 0

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
                if occtime[:8] not in ecard_occtime:
                    ecard_occtime.append(occtime[:8])
                
                tranamt = int(item['sign_tranamt']) / 100.0
                tranname = item['tranname'].replace('\r', '').replace('\n', '').strip()
                mercname = item['mercname'].replace('\r', '').replace('\n', '').strip()
                trancode = item['trancode'].replace('\r', '').replace('\n', '').strip()

                # ecard process
                if tranamt < 0 and tranamt < ecard_biggest['tranamt']:
                    ecard_biggest['occtime'] = occtime
                    ecard_biggest['mercname'] = mercname
                    ecard_biggest['tranamt'] = tranamt
                
                if tranamt < 0:
                    daytime = occtime[:8]
                    if daytime not in ecard_day.keys():
                        ecard_day[daytime] = 0
                    else:
                        ecard_day[daytime] += -1 * tranamt
                    
                if trancode == '15':
                    if mercname.find('水控') != -1 or mercname.find('水电费') != -1:
                        ecard_shower += 1
                    elif mercname.find('超市') or mercname.find('商贸') != -1:
                        ecard_market += 1
                    elif mercname.find('出国成绩') != -1:
                        pass
                    else:
                        ecard_normal += 1
                        if mercname not in ecard_dining.keys():
                            ecard_dining[mercname] = 1
                        else:
                            ecard_dining[mercname] += 1
                        
                if trancode == '16':
                    ecard_bank += 1

                if trancode == '94':
                    if mercname.find('网上缴费') != -1:
                        ecard_web += 1
                    elif mercname.find('水控') != -1 or mercname.find('水电费') != -1:
                        ecard_shower += 1
                    else:
                        ecard_normal += 1
                        if mercname not in ecard_dining.keys():
                            ecard_dining[mercname] = 1
                        else:
                            ecard_dining[mercname] += 1

                if trancode == '1A':
                    ecard_alipay += 1

                if mercname not in ecard_merc.keys():
                    ecard_merc[mercname] = 1
                else:
                    ecard_merc[mercname] += 1

        q.put((ecard_biggest, ecard_day, ecard_shower, ecard_market, ecard_normal, \
                ecard_bank, ecard_merc, ecard_dining, ecard_occtime, ecard_alipay, ecard_web))
            
    @retry(2)
    def _get_ecard(self, response):
        sess = copy.deepcopy(self._session)

        i = 1
        params = {
                'curpage': '{}'.format(i),
                'pagesize': '50',
                'account': '{}'.format(self._account),
                'queryStart': self._query_start,
                'queryEnd': self._query_end
            }
        
        res = self._get(sess=sess, url='http://mapp.zju.edu.cn/lightapp/lightapp/getHistoryConsumption', params=params).json()
        pages = int(int(res['data']['query_his_total']['rowcount']) / int(res['data']['query_his_total']['pagesize']))
        
        ecard_biggest = {
            'occtime': '',
            'mercname': '',
            'tranamt': 0.0
        }
        ecard_day, ecard_merc, ecard_dining = {}, {}, {}
        ecard_occtime = []
        ecard_shower, ecard_market, ecard_normal, ecard_bank, ecard_alipay, ecard_web = 0, 0, 0, 0, 0, 0

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
            ecard_biggest_t, ecard_day_t, ecard_shower_t, ecard_market_t, ecard_normal_t, ecard_bank_t, \
                ecard_merc_t, ecard_dining_t, ecard_occtime_t, ecard_alipay_t, ecard_web_t = q.get()
            ecard_biggest = ecard_biggest_t if ecard_biggest_t['tranamt'] < ecard_biggest['tranamt'] else ecard_biggest
            ecard_day.update(ecard_day_t)
            ecard_alipay += ecard_alipay_t
            ecard_shower += ecard_shower_t
            ecard_normal += ecard_normal_t
            ecard_market += ecard_market_t
            ecard_bank += ecard_bank_t
            ecard_web += ecard_web_t
            for key, value in ecard_merc_t.items():
                if key not in ecard_merc.keys():
                    ecard_merc[key] = value
                else:
                    ecard_merc[key] += value
            for key, value in ecard_dining_t.items():
                if key not in ecard_dining.keys():
                    ecard_dining[key] = value
                else:
                    ecard_dining[key] += value
            for i in ecard_occtime_t:
                if i not in ecard_occtime:
                    ecard_occtime.append(i)

        ecard = {}

        # ecard_occtime.sort()
        # logger.info('{} {}'.format(ecard_occtime[0], ecard_occtime[-1]))

        ecard_merc_list = sorted(ecard_merc.items(), key=lambda d:d[1], reverse=True)
        ecard_most = [{'mercname': i[0], 'count': i[1]} for i in ecard_merc_list[:3]]

        ecard_dining_list = sorted(ecard_dining.items(), key=lambda d:d[1], reverse=True)
        ecard_dining = [{'mercname': i[0], 'count': i[1]} for i in ecard_dining_list[:2]]

        occtime = ecard_biggest['occtime']
        ecard_biggest['occtime'] = '{}-{}-{} {}:{}:{}'.format(occtime[0:4], occtime[4:6], occtime[6:8], occtime[8:10], occtime[10:12], occtime[12:14])
        ecard_biggest['tranamt'] = -1 * ecard_biggest['tranamt']

        ecard_day = sorted(ecard_day.items(), key=lambda d:d[1], reverse=True)
        ecard['day'] = {
            'time': '{}-{}-{}'.format(ecard_day[0][0][0:4], ecard_day[0][0][4:6], ecard_day[0][0][6:8]),
            'count': ecard_day[0][1]
        }
        # ecard['merc'] = ecard_merc_list
        ecard['shower'] = ecard_shower
        ecard['web'] = ecard_web
        ecard['bank'] = ecard_bank
        ecard['normal'] = ecard_normal
        ecard['alipay'] = ecard_alipay
        ecard['market'] = ecard_market
        ecard['biggest'] = ecard_biggest
        ecard['most'] = ecard_most
        ecard['dining'] = ecard_dining
        ecard['total'] = len(ecard_merc_list)
        ecard['num'] = len(ecard_occtime)

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
        viewstate = re.search('name="__VIEWSTATE" value=".*?"', res.text).group(0)[26:-1]
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
            viewstate = re.search(
                'name="__VIEWSTATE" value=".*?"', res.text).group(0)[26:-1]
            data = {
                '__EVENTTARGET': 'xnd',
                '__VIEWSTATE': viewstate,
                'xnd': '{}-{}'.format(base-i, base-i+1),
            }
            res = self._post(sess=sess, url='http://jwbinfosys.zju.edu.cn/xskbcx.aspx?xh={}'.format(self._stuid), data=data)
            self._get_jwbinfosys_util(res, teacher2num, semester2num, teacher2course, '{}-{} {}'.format(base-i, base-i+1, left_semester.replace('、', '')))

            # xqd, change semester
            viewstate = re.search('name="__VIEWSTATE" value=".*?"', res.text).group(0)[26:-1]

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

    @retry(2)
    def _get_jwbinfosys(self, response):
        # ajax
        # get base cookie
        sess = copy.deepcopy(self._session)

        jwbinfosys = {}

        # prefetch
        self._get(sess=sess, url='http://jwbinfosys.zju.edu.cn/default2.aspx')

        # major grade
        res = self._get(sess=sess, url='http://jwbinfosys.zju.edu.cn/xscj_zg.aspx?xh={}'.format(self._stuid))
        tds = re.findall('<tr[\S\s]*?</tr>', res.text)[1:]
        jwbinfosys['major_count'] = len(tds)

        # all grade
        res = self._get(sess=sess, url='http://jwbinfosys.zju.edu.cn/xscj.aspx?xh={}'.format(self._stuid))
        # constant
        viewstate = re.search('name="__VIEWSTATE" value=".*?"', res.text).group(0)[26:-1]
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
            total_credit += float(credit)

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
                if int(score):
                    course2score[course_name] = int(score)
            except Exception as e:
                # here, always right?
                course2score[course_name] = 95-10*(5-float(gp))
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

        semester2num = sorted(semester2num.items(), key=lambda d:d[1],reverse=True)
        jwbinfosys['semester'] = {
            'name': semester2num[0][0],
            'count': semester2num[0][1],
            'avg': int(sum([i[1] for i in semester2num]) / len(semester2num))
        }

        response['jwbinfosys'] = jwbinfosys

    def _get_library_util(self, date):
        date1 = datetime.datetime.strptime(date, '%Y%m%d')
        delta = datetime.timedelta(days=-40)
        date2 = date1 + delta
        return date2.strftime('%Y-%m-%d')

    def _get_library_topic(self, sess, start, end, topic_urls, q):
        topic2num = {}
        for i in range(start, end):
            topic_url = topic_urls[i]
            res = self._get(sess=sess, url=topic_url)
            res.encoding = 'utf-8'
            soup = bs4.BeautifulSoup(res.text, 'html.parser')
            table = soup.findAll('table')[-2]
            trs = table.findAll('tr')[1:]
            for tr in trs:
                tds = tr.findAll('td')
                for i in range(0, len(tds)):
                    if (tds[i].text).find('主题') != -1:
                        try:
                            for topic in ("".join(tds[i+1].text.strip('\n').split())).split('-'):
                                if topic not in topic2num.keys():
                                    topic2num[topic] = 1
                                else:
                                    topic2num[topic] += 1
                            break
                        except Exception:
                            break
        q.put((topic2num))

    @retry(2)
    def _get_library(self, response):
        # ISO-8859-1
        sess = copy.deepcopy(self._session)
        res = self._get(sess=sess, url='http://webpac.zju.edu.cn/zjusso')
        res.encoding = 'utf-8'
        # ?

        library = {}
        try:
            a = re.search('<a href=.*?func=bor-history-loan.*?</a>', res.text).group(0)
        except Exception as e:
            library['total_count'] = -1
            response['library'] = library
            return

        href = re.search('\(.*?\)', a).group(0)[2:-2]
        res = self._get(sess=sess, url=href)
        res.encoding = 'utf-8'
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        table = soup.findAll('table')[-1]
        trs = table.findAll('tr')[1:]

        book_info = []
        topic_urls = []
        author2num, place2num, topic2num = {}, {}, {}

        try:
            for tr in trs:
                tds = tr.findAll('td')
                author, book_name, date, place = tds[1].text.strip(',').strip('，'), tds[2].text, tds[4].text, tds[-1].text
                book_info.append((author, book_name, date))

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
                # res = self._get(sess=sess, url=topic_url)
                # res.encoding = 'utf-8'
                # soup = bs4.BeautifulSoup(res.text, 'html.parser')
                # table = soup.findAll('table')[-2]
                # trs = table.findAll('tr')[1:]
                # for tr in trs:
                #     tds = tr.findAll('td')
                #     for i in range(0, len(tds)):
                #         if (tds[i].text).find('主题') != -1:
                #             try:
                #                 for topic in ("".join(tds[i+1].text.strip('\n').split())).split('-'):
                #                     if topic not in topic2num.keys():
                #                         topic2num[topic] = 1
                #                     else:
                #                         topic2num[topic] += 1
                #                 break
                #             except Exception as e:
                #                 break
                    
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
            library['total_count'] = 0
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
            topic2num_t =  q.get()
            for key, value in topic2num_t.items():
                if key not in topic2num.keys():
                    topic2num[key] = value
                else:
                    topic2num[key] += value

        topic2num = sorted(topic2num.items(), key=lambda d:d[1] ,reverse=True)
        place2num = sorted(place2num.items(), key=lambda d:d[1],reverse=True)
        author2num = sorted(author2num.items(), key=lambda d:d[1],reverse=True)

        library['total_count'] = len(book_info)
        library['author'] = {
            'name': author2num[0][0],
            'count': author2num[0][1]
        }
        library['first_book'] = first_book
        library['last_book'] = last_book
        library['place'] = {
            'count': len(place2num),
            'most_name': place2num[0][0]
        }
        library['topic'] = [i[0] for i in topic2num[:6]]

        response['library'] = library

    def _get_cc98_headers(self, token=True):
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
            'Connection': 'keep-alive',
            'authorization': '%s %s' % (myredis.getex('token_type'), myredis.getex('token'))
        } if token else {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
            'Connection': 'keep-alive'
        }

    def _get_cc98_token(self):
        # already exists
        if myredis.getex('token') != None:
            return
        # no token, but refresh_token exists
        if myredis.getex('refresh_token') != None:
            data = {
                'grant_type': 'refresh_token',
                'client_id': self._cc98_config['client_id'],
                'client_secret': self._cc98_config['client_secret'],
                'refresh_token': myredis.getex('refresh_token'),
            }
            res = requests.post(url='https://openid.cc98.org/connect/token', data=data, headers=self._get_cc98_headers(token=False)).json()
            myredis.setex('token', res['access_token'], res['expires_in'])
            myredis.setex('token_type', res['token_type'], res['expires_in'])
            # here, refresh_token: 30 days, access_token: 1 hour
            myredis.setex('refresh_token', res['refresh_token'], 24 * 30 * res['expires_in'])

            return

        data = {
            'client_id': self._cc98_config['client_id'],
            'client_secret': self._cc98_config['client_secret'],
            'grant_type': 'password',
            'username': self._cc98_config['username'],
            'password': self._cc98_config['password'],
        }
        res = requests.post(url='https://openid.cc98.org/connect/token', data=data, headers=self._get_cc98_headers(token=False)).json()


        myredis.setex('token', res['access_token'], res['expires_in'])
        myredis.setex('token_type', res['token_type'], res['expires_in'])
        # here, refresh_token: 30 days, access_token: 1 hour
        myredis.setex('refresh_token', res['refresh_token'], 24 * 30 * res['expires_in'])

    def _get_cc98_util(self, sess, title, q):
        post_count, follow_count, fan_count, like_count, pop_count = [0] * 5
        register_time = "0000-00-00"

        # username
        name = title.text.strip().strip('\n').strip()
        res = self._get(sess=sess, url="https://api-v2.cc98.org/user/name/{}".format(name)).json()

        cc98_id = res['id']
        post_count += int(res['postCount'])
        follow_count += int(res['followCount'])
        fan_count += int(res['fanCount'])
        like_count += int(res['receivedLikeCount'])
        pop_count += int(res['popularity'])
        register_time = res['registerTime'][:10]

        recent_topics = {}
        recent_topics_board = {}

        start = 0
        while True:
            try:
                res = requests.get(url="https://api-v2.cc98.org/user/{}/recent-topic?from={}&size=20".format(cc98_id, 20*start), headers=self._get_cc98_headers()).json()
                if not len(res):
                    break
                for i in res:
                    time, board, title = i['time'], i['boardName'], i['title']
                    recent_topics[i['time']] = i['title']
                    if board not in recent_topics_board.keys():
                        recent_topics_board[board] = 1
                    else:
                        recent_topics_board[board] += 1
            except Exception as e:
                break
            start += 1
    
        q.put((post_count, follow_count, fan_count, like_count, pop_count, register_time, recent_topics, recent_topics_board))

    @retry(2)
    def _get_cc98(self, response):
        sess = copy.deepcopy(self._session)

        res = self._get(sess=sess, url='https://account.cc98.org/My')
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        tables = soup.findAll(attrs={'class': "table table-sm"})
        titles = soup.findAll(attrs={'class': "card-title"})

        cc98 = {}
        cc98['gender'] = self._gender
        cc98['count'] = len(tables)
        cc98['login_times'] = 0
        cc98['comment_times'] = 0

        for table in tables:
            trs = table.findAll('tr')
            infos = []
            for tr in trs:
                tds = tr.findAll('td')
                infos.append(tds[1].text)
            register_time, last_login, login_times, comment_times = infos[0], infos[1], infos[2], infos[3]
            cc98['login_times'] += int(login_times)
            cc98['comment_times'] += int(comment_times)

        post_count, follow_count, fan_count, like_count, pop_count = [0] * 5
        register_time = '2020-01-01'
        recent_topics = {}
        recent_topics_board = {}

        t = []
        q = queue.Queue()

        # need token
        self._get_cc98_token()
        for title in titles:
            t.append(threading.Thread(target=zju._get_cc98_util,args=(self, sess, title, q)))
        try:
            for i in t:
                i.start()
            for i in t:
                i.join()
        except Exception as e:
            raise e

        while not q.empty():
            post_count_t, follow_count_t, fan_count_t, like_count_t, pop_count_t, \
                    register_time_t, recent_topics_t, recent_topics_board_t =  q.get()
            post_count += post_count_t
            follow_count += follow_count_t
            fan_count += fan_count_t
            like_count += like_count_t
            pop_count += pop_count_t
            register_time = register_time_t if register_time_t < register_time else register_time
            recent_topics.update(recent_topics_t)
            for key, value in recent_topics_board_t.items():
                if key not in recent_topics_board.keys():
                    recent_topics_board[key] = value
                else:
                    recent_topics_board[key] += value


        cc98['post_count'] = len(list(recent_topics))
        cc98['follow_count'] = follow_count
        cc98['fan_count'] = fan_count
        cc98['like_count'] = like_count
        cc98['pop_count'] = pop_count
        cc98['register_time'] = register_time

        try:
            recent_topics_list = sorted(recent_topics.items(), key=lambda d:d[0], reverse=False)
            trans_topic = [{'time': i[0][:10], 'title': i[1]} for i in recent_topics_list]
            first_topic = trans_topic[0]
            last_topic = trans_topic[-1]

            recent_topics_board_list = sorted(recent_topics_board.items(), key=lambda d:d[1], reverse=True)
            post_most_board = [{'board': i[0], 'count': i[1]} for i in recent_topics_board_list[:1]][0]

            cc98['topic_count'] = len(recent_topics_list)
            cc98['first_topic'] = first_topic
            cc98['last_topic'] = last_topic
            cc98['post_most'] = post_most_board
        except Exception:
            cc98['first_topic'] = {}
            cc98['post_most'] = {}

        response['cc98'] =  cc98

    @retry(2)
    def _get_sport(self, response):
        sess = copy.deepcopy(self._session)

        res = self._get(sess=sess, url='http://www.tyys.zju.edu.cn/ggtypt')
        res = self._get(sess=sess, url='http://www.tyys.zju.edu.cn/pft/loginto')
        res = self._get(sess=sess, url='http://www.tyys.zju.edu.cn/pft/myresult')

        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        table = soup.find(id='dataTables-main')
        tbody = table.find('tbody')
        trs = tbody.findAll('tr')

        years, heights, weights, bmis, scores, runs = [], [], [], [], [], []

        for tr in trs:
            tds = tr.findAll('td')
            tds = [i.text.strip() for i in tds]
            if tds[-1] == '免测' or tds[-1] == '暂无':
                continue
            else:
                score = float(tds[-1]) 
            try:
                year, bmi, height, weight, run = tds[0], tds[2], tds[3], tds[4], tds[9].split('/')[0].replace('.', "'")
            except Exception as e:
                continue
            # format: 2018-2019学年
            year = '{}-{}'.format(year[2:4], year[7:9])
            years.append(year)
            heights.append(height)
            weights.append(weight)
            scores.append(score)
            runs.append(run)
            bmis.append(bmi)

        years = years[::-1]
        heights = heights[::-1]
        weights = weights[::-1]
        bmis = bmis[::-1]
        runs = runs[::-1]

        sport = {}
        sport['height'] = heights
        sport['weight'] = weights
        sport['year'] = years

        try:
            sport['score'] = max(scores)
        except Exception:
            sport['score'] = 0
        sport['bmi'] = bmis
        sport['run'] = runs

        response['sport'] =  sport

if __name__ == '__main__':
    pass
