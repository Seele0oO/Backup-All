import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, List
from core.logger import Logger
from core.config import ConfigManager
from utils.warning import WarningHint
from importlib import import_module
from core.backup_base import BackupPlugin
import time

class BackupSystem:
    def __init__(self, config_file: str):
        self.logger = Logger()
        self.config = ConfigManager(config_file, self.logger)
        self._init_python_path()
        self.plugins = self._load_plugins()

    def _init_python_path(self):
        """初始化 Python 导入路径"""
        project_root = Path(__file__).parent.absolute()
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        self.logger.debug(f"Python path: {sys.path}")

    def _load_plugins(self) -> Dict[str, BackupPlugin]:
        """加载所有备份插件"""
        plugins = {}
        # 定义插件类名映射
        plugin_classes = {
            'mongodb': 'MongoDBBackup',
            'mysql': 'MySQLBackup',
            'folder': 'FolderBackup',
            'volume': 'VolumeBackup'
        }
        
        for plugin_type, class_name in plugin_classes.items():
            try:
                module_name = f"plugins.{plugin_type}_backup"
                self.logger.debug(f"Attempting to import {module_name}")
                
                module = import_module(module_name)
                self.logger.debug(f"Looking for class {class_name}")
                
                plugin_class = getattr(module, class_name)
                plugin = plugin_class(self.logger, self.config.backup_root)
                plugins[plugin_type] = plugin
                
                self.logger.info(f"Successfully loaded plugin: {plugin_type}")
            except Exception as e:
                self.logger.error(f"Failed to load plugin {plugin_type}: {str(e)}")
                import traceback
                self.logger.debug(f"Traceback: {traceback.format_exc()}")

        return plugins
            
    def _cleanup_old_backups(self):
        """清理旧备份"""
        try:
            # 1. 首先删除过期的备份文件
            cutoff_time = time.time() - (self.config.backup_keep_days * 24 * 3600)
            for path in Path(self.config.backup_root).rglob('*'):
                if path.is_file() and path.suffix in ['.tar.gz', '.tar', '.gz']:
                    if path.stat().st_mtime < cutoff_time:
                        path.unlink()
                        self.logger.debug(f"Deleted old backup: {path}")

            # 2. 然后自下而上清理空目录
            empty_dirs = set()
            for path in sorted(Path(self.config.backup_root).rglob('*'), reverse=True):
                if path.is_dir():
                    if not any(path.iterdir()):  # 如果目录为空
                        path.rmdir()
                        empty_dirs.add(path)
                        self.logger.debug(f"Removed empty directory: {path}")

            if empty_dirs:
                self.logger.info(f"Cleaned up {len(empty_dirs)} empty directories")
            self.logger.info("Cleanup completed successfully")

        except Exception as e:
            self.logger.error(f"Cleanup failed: {str(e)}")

    def run(self):
        """运行备份任务"""
        WarningHint.countdown()
        
        # 执行数据库任务
        for db_task in self.config.database_tasks:
            plugin = self.plugins.get(db_task.type)
            if plugin:
                try:
                    plugin.backup(db_task)
                except Exception as e:
                    self.logger.error(f"{db_task.type} backup failed: {str(e)}")
            else:
                self.logger.error(f"No plugin found for database type: {db_task.type}")

        # 执行文件夹任务
        for folder_task in self.config.folder_tasks:
            if 'folder' in self.plugins:
                try:
                    self.plugins['folder'].backup(folder_task)
                except Exception as e:
                    self.logger.error(f"Folder backup failed: {str(e)}")
            else:
                self.logger.error("Folder backup plugin not found")

        # 执行卷任务
        for volume_task in self.config.volume_tasks:
            if 'volume' in self.plugins:
                try:
                    self.plugins['volume'].backup(volume_task)
                except Exception as e:
                    self.logger.error(f"Volume backup failed: {str(e)}")
            else:
                self.logger.error("Volume backup plugin not found")

        # 执行清理
        self._cleanup_old_backups()

def check_dependencies(config: ConfigManager):
    """根据配置文件检查必要的命令行工具"""
    required_commands = {
        'tar': 'tar command',
        'docker': 'Docker command line'
    }
    
    # 检查数据库任务的依赖
    for task in config.database_tasks:
        if not task.docker.enabled:  # 只有非docker任务才需要检查数据库工具
            if task.type == 'mongodb':
                required_commands['mongodump'] = 'MongoDB tools'
            elif task.type == 'mysql':
                required_commands['mysqldump'] = 'MySQL client'
    
    # 检查依赖是否存在
    missing = []
    for cmd, name in required_commands.items():
        if shutil.which(cmd) is None:
            missing.append(name)
    
    if missing:
        print(f"Missing required dependencies: {', '.join(missing)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Modular Backup System')
    parser.add_argument('-f', '--file', help='Specify the configuration file and run tasks')
    parser.add_argument('-t', '--test', help='Test the configuration file')
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    logger = Logger()

    try:
        if args.file:
            config = ConfigManager(args.file, logger)
            check_dependencies(config)
            logger.info(f"Using config file: {args.file}")
            logger.info(f"Backup root: {config.backup_root}")
            logger.info(f"Backup keep days: {config.backup_keep_days}")
            
            total_tasks = (
                len(config.database_tasks) + 
                len(config.folder_tasks) + 
                len(config.volume_tasks)
            )
            logger.info(f"Found {total_tasks} tasks")
            
            backup_system = BackupSystem(args.file)
            backup_system.run()
        elif args.test:
            config = ConfigManager(args.test, logger)
            check_dependencies(config)
            logger.info(f"Config file validated successfully: {args.test}")
            logger.info(f"Backup root: {config.backup_root}")
            logger.info(f"Backup keep days: {config.backup_keep_days}")
            
            # 显示数据库任务信息
            for task in config.database_tasks:
                logger.info(
                    f"Database task: type={task.type}, "
                    f"database={task.database}, "
                    f"docker={'enabled' if task.docker.enabled else 'disabled'}"
                )
            
            # 显示文件夹任务信息
            for task in config.folder_tasks:
                logger.info(
                    f"Folder task: path={task.path}, "
                    f"exclude_count={len(task.exclude) if task.exclude else 0}"
                )
            
            # 显示卷任务信息
            for task in config.volume_tasks:
                logger.info(f"Volume task: name={task.name}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
