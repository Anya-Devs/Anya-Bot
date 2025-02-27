import logging
import os
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler

class Logger:
    """A custom logger class that handles both file and console logging.
    
    This logger creates rotating log files with timestamps and configurable settings.
    It provides methods for different logging levels and formats logs differently
    for file vs console output.
    
    Attributes:
        logger (logging.Logger): The underlying Python logger instance
        
    Args:
        name (str): The name of the logger. Defaults to "bot"
        log_dir (str): Directory to store log files. Defaults to "logs"
        max_bytes (int): Maximum size of each log file before rotation. Defaults to 5MB
        backup_count (int): Number of backup log files to keep. Defaults to 5
    """

    def __init__(self, name: str = "bot", log_dir: str = ".logs", max_bytes: int = 5_242_880, backup_count: int = 5) -> None:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        self.logger: logging.Logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        file_formatter: logging.Formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter: logging.Formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )

        log_file: str = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        file_handler: RotatingFileHandler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)

        console_handler: logging.StreamHandler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, message: str) -> None:
        """Log an info level message.
        
        Args:
            message (str): The message to log
        """
        self.logger.info(message)

    def warning(self, message: str) -> None:
        """Log a warning level message.
        
        Args:
            message (str): The message to log
        """
        self.logger.warning(message)

    def error(self, message: str) -> None:
        """Log an error level message.
        
        Args:
            message (str): The message to log
        """
        self.logger.error(message)

    def debug(self, message: str) -> None:
        """Log a debug level message.
        
        Args:
            message (str): The message to log
        """
        self.logger.debug(message)

    def critical(self, message: str) -> None:
        """Log a critical level message.
        
        Args:
            message (str): The message to log
        """
        self.logger.critical(message)