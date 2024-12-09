from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional
from core.logger import Logger

class BackupPlugin(ABC):
    def __init__(self, logger: Logger, backup_root: Path):
        self.logger = logger
        self.backup_root = backup_root

    @abstractmethod
    def backup(self, task_config: Dict) -> bool:
        """执行备份任务"""
        pass

    @abstractmethod
    def get_type(self) -> str:
        """返回插件类型"""
        pass

    def create_folder(self, folder: Path) -> Path:
        """创建文件夹并返回Path对象"""
        folder.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Ensured folder exists: {folder}")
        return folder