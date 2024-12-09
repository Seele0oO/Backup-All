import logging
import colorlog
import sys

class Logger:
    def __init__(self, log_file: str = "./script.log"):
        self.logger = logging.getLogger('backup')
        self.logger.setLevel(logging.DEBUG)
        
        color_formatter = colorlog.ColoredFormatter(
            '%(asctime)s %(log_color)s[%(levelname)s]%(reset)s %(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        
        console = logging.StreamHandler()
        console.setFormatter(color_formatter)
        self.logger.addHandler(console)
        
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def debug(self, msg: str): self.logger.debug(msg)
    def info(self, msg: str): self.logger.info(msg)
    def warning(self, msg: str): self.logger.warning(msg)
    def error(self, msg: str): 
        self.logger.error(msg)
        sys.exit(1)
    def critical(self, msg: str):
        self.logger.critical(msg)
        sys.exit(1)