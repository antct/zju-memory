import logging

logging.basicConfig(filename='./log', format='%(asctime)s - %(levelname)s - %(threadName)s: %(message)s')
logging.root.setLevel(level=logging.INFO)
logger = logging.getLogger()