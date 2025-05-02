import logging
import colorlog
import colorama

# Initialize colorama for colored terminal output
colorama.init()

# Define logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  

# Set up the log handler
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)

logger.addHandler(handler)
