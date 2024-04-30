import logging
import colorama
import colorlog
from colorama import Fore, Style
from datetime import datetime


colorama.init()

# Set up logging with color
logger = colorlog.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }))
logger.addHandler(handler)
