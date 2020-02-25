FROM python:3.6.7
COPY memory /memory
WORKDIR /memory
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
ENTRYPOINT ["python"]
CMD ["app.py"]