# ZJU Memory

![](https://img.shields.io/github/stars/conv1d/zju-memory) ![](https://img.shields.io/github/forks/conv1d/zju-memory) ![](https://img.shields.io/badge/pv-59292-blue) ![](https://img.shields.io/badge/uv-16280-blue) ![](https://img.shields.io/github/issues/conv1d/zju-memory)

人生到处知何似，应似飞鸿踏雪泥。离开之前，重拾你的浙里记忆。

## Run

> Fill in `memory/config.ini` first

```bash
cd memory
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

```
docker build -t memory:1.0 .
docker run -it --rm -p 5000:5000 memory:1.0
```

> View it in your browser → http://localhost:5000/

## Pics

紫金港竺像 - 玉泉毛像 - 紫金港启真湖畔 - 之江礼堂 - 华家池水 - 西溪图书馆 - 海宁一角 - 舟山灯塔

## Snapshots

![](snapshot.jpg)
