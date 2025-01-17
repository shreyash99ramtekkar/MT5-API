from constants import LoggerConstants
import logging,logging.config;
import yaml

class MT5ApiLogger:
    def __init__(self):
        with open(LoggerConstants.CONFIG_PATH,  "r") as f:
            yaml_config = yaml.safe_load(f.read())
            logging.config.dictConfig(yaml_config)
    
    def get_logger(self,name):
        return logging.getLogger(name)