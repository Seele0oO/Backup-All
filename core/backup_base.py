from pathlib import Path
from datetime import datetime
from typing import Dict, Union
from abc import ABC, abstractmethod
from core.logger import Logger
from core.config import DatabaseConfig, FolderConfig, VolumeConfig

class BackupPlugin(ABC):
    def __init__(self, logger: Logger, backup_root: Path):
        self.logger = logger
        self.backup_root = backup_root

    @abstractmethod
    def backup(self, task_config: Union[DatabaseConfig, FolderConfig, VolumeConfig]) -> bool:
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

    def _prepare_backup_path(self, task_config: Union[DatabaseConfig, FolderConfig, VolumeConfig]) -> Path:
        """准备备份目录
        
        命名规则：
        {type}_{identifier}/{date}
        例如：
        mongodb_container-name_dbname/20241209
        mysql_container-name_dbname/20241209
        folder_foldername/20241209
        volume_volumename/20241209
        """
        timestamp = datetime.now().strftime('%Y%m%d')
        
        if isinstance(task_config, DatabaseConfig):
            identifier = (
                f"{task_config.docker.container}_{task_config.database}"
                if task_config.docker.enabled
                else f"{task_config.host}_{task_config.database}"
            )
            backup_name = f"{task_config.type}_{identifier}"
            
        elif isinstance(task_config, FolderConfig):
            identifier = Path(task_config.path).name
            backup_name = f"folder_{identifier}"
            
        elif isinstance(task_config, VolumeConfig):
            backup_name = f"volume_{task_config.name}"
            
        else:
            raise ValueError(f"Unknown config type: {type(task_config)}")

        backup_path = self.backup_root / backup_name / timestamp
        self.create_folder(backup_path)
        
        self.logger.debug(f"Prepared backup path: {backup_path}")
        return backup_path