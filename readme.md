# zju-memory

人生到处知何似，应似飞鸿踏雪泥。离开之前，重拾你的浙里记忆。

## run

```python
from core import zju
resp = {}
sess = zju(
    username=your_username,
    password=your_password,
    cc98_username=your_cc98_username,
    cc98_password=your_cc98_password,
)
try:
    sess.login()
    sess.go(resp)
    print(resp)
except Exception as e:
    raise e
```

## pics

紫金港竺像 - 玉泉毛像 - 紫金港启真湖畔 - 之江礼堂 - 华家池水 - 西溪图书馆 - 海宁一角 - 舟山灯塔


