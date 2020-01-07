# zju-memory

浙大记忆，献给ZJU的毕业礼物~

## Motivation

浙大通行证背后有着各式各样的内网，你刷过的每一笔校园卡流水，上过的每一门课，遇见的每一位老师，借阅过的每一本图书，都在其间留存下痕迹。雪泥鸿爪，离开之前，重拾你的浙里记忆。

## Techstack

1. 登录方式 账号密码方式 or 我的浙大扫码登录(相对安全)
2. 前端 H5 animate.js H5fullpage.js echarts.js overhang.js preload.js wx.js(share)...
3. 后端 Flask uwsgi
4. 反向代理 nginx
5. 内网穿透 frp

## Run

> 运行前请配置backend/cc98.config，backend/wx.config非必须。

```python
from core import zju
username = ''
password = ''
resp = {}
sess = zju(username, password)
try:
    sess.login()
    sess.go(resp)
    print(resp)
except Exception as e:
    raise e
```

## Snapshots

紫金港竺像 - 玉泉毛像 - 紫金港启真湖 - 之江礼堂 - 华家池水 - 西溪图书馆 - 海宁一角 - 舟山灯塔
