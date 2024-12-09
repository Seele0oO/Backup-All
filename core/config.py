from pathlib import Path
from typing import Dict, List, Optional, Union
import json
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DockerConfig:
    enabled: bool
    container: Optional[str] = None

@dataclass
class AuthConfig:
    username: str
    password: str

@dataclass
class DatabaseConfig:
    type: str  # mongodb 或 mysql
    docker: DockerConfig
    host: str
    port: int
    database: str
    auth: Optional[AuthConfig] = None
    exclude: List[str] = None

@dataclass
class FolderConfig:
    path: Path
    exclude: List[str] = None

@dataclass
class VolumeConfig:
    name: str

@dataclass
class BackupSettings:
    backup_root: Path
    backup_keep_days: int

class ConfigManager:
    def __init__(self, config_file: str, logger):
        self.logger = logger
        self.config_file = config_file
        self.settings = None
        self.database_tasks = []
        self.folder_tasks = []
        self.volume_tasks = []
        self._load_config()

    def _load_config(self) -> None:
        """加载并解析配置文件"""
        try:
            with open(self.config_file) as f:
                config = json.load(f)

            # 解析基本设置
            self.settings = BackupSettings(
                backup_root=Path(config['settings']['backup_root']),
                backup_keep_days=int(config['settings']['backup_keep_days'])
            )

            # 解析数据库任务
            for db_type, dbs in config['tasks']['databases'].items():
                for db_config in dbs:
                    self.database_tasks.append(self._parse_database_config(db_type, db_config))

            # 解析文件夹任务
            for folder in config['tasks'].get('folders', []):
                self.folder_tasks.append(self._parse_folder_config(folder))

            # 解析卷任务
            for volume in config['tasks'].get('volumes', []):
                self.volume_tasks.append(self._parse_volume_config(volume))

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON format in {self.config_file}: {str(e)}")
            raise
        except KeyError as e:
            self.logger.error(f"Missing required configuration key: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            raise

    def _parse_database_config(self, db_type: str, config: Dict) -> DatabaseConfig:
        """解析数据库配置"""
        docker_config = DockerConfig(
            enabled=config['docker']['enabled'],
            container=config['docker'].get('container') if config['docker']['enabled'] else None
        )

        auth_config = None
        if 'auth' in config:
            auth_config = AuthConfig(
                username=config['auth']['username'],
                password=config['auth']['password']
            )

        return DatabaseConfig(
            type=db_type,
            docker=docker_config,
            host=config['host'],
            port=int(config['port']),
            database=config['database'],
            auth=auth_config,
            exclude=config.get('exclude', [])
        )

    def _parse_folder_config(self, config: Dict) -> FolderConfig:
        """解析文件夹配置"""
        return FolderConfig(
            path=Path(config['path']),
            exclude=config.get('exclude', [])
        )

    def _parse_volume_config(self, config: Dict) -> VolumeConfig:
        """解析卷配置"""
        return VolumeConfig(name=config['name'])

    @property
    def backup_root(self) -> Path:
        return self.settings.backup_root

    @property
    def backup_keep_days(self) -> int:
        return self.settings.backup_keep_days

    def validate(self) -> bool:
        """验证配置的有效性"""
        try:
            # 验证备份根目录
            if not self.backup_root.parent.exists():
                self.logger.error(f"Backup root parent directory does not exist: {self.backup_root.parent}")
                return False

            # 验证数据库配置
            for db in self.database_tasks:
                if db.docker.enabled and not db.docker.container:
                    self.logger.error(f"Docker enabled but no container specified for {db.type} database {db.database}")
                    return False

            # 验证文件夹配置
            for folder in self.folder_tasks:
                if not folder.path.is_absolute():
                    folder.path = Path.cwd() / folder.path

                if not folder.path.exists():
                    self.logger.error(f"Folder path does not exist: {folder.path}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {str(e)}")
            return False

    def get_task_configs(self) -> List[Dict]:
        """获取所有任务的配置"""
        tasks = []

        # 转换数据库任务
        for db in self.database_tasks:
            task = {
                'type': db.type,
                'docker': {
                    'is-docker': db.docker.enabled,
                    'container_name': db.docker.container
                } if db.docker.enabled else None,
                'host': db.host,
                'port': str(db.port),
                'database': db.database
            }
            if db.auth:
                task.update({
                    'username': db.auth.username,
                    'password': db.auth.password
                })
            if db.exclude:
                task['excludeCollection'] = db.exclude
            tasks.append(task)

        # 转换文件夹任务
        for folder in self.folder_tasks:
            tasks.append({
                'type': 'folder',
                'path': str(folder.path),
                'exclude': folder.exclude
            })

        # 转换卷任务
        for volume in self.volume_tasks:
            tasks.append({
                'type': 'volume',
                'docker': {
                    'is-docker': True,
                    'volume_name': volume.name
                }
            })

        return tasks
