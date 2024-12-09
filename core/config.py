import json
from pathlib import Path
from typing import Dict, Optional
from core.logger import Logger

class ConfigManager:
    def __init__(self, config_file: str, logger: Logger):
        self.config_file = config_file
        self.logger = logger
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        try:
            with open(self.config_file) as f:
                config = json.load(f)
                if not self._validate_config(config):
                    raise ValueError("Invalid configuration format")
                return config
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON format in {self.config_file}")
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_file}")
        except ValueError as e:
            self.logger.error(str(e))

    def _validate_config(self, config: Dict) -> bool:
        """验证配置文件格式"""
        required_keys = ['settings', 'tasks']
        if not all(key in config for key in required_keys):
            return False
        if not config['settings'] or not isinstance(config['settings'], list):
            return False
        if 'backup_root' not in config['settings'][0]:
            return False
        return True

    @property
    def backup_root(self) -> Path:
        return Path(self.config['settings'][0]['backup_root'])

    @property
    def backup_keep_days(self) -> int:
        return int(self.config['settings'][0]['backup_keep_days'])

    @property
    def tasks(self) -> list:
        return self.config['tasks']