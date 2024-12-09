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
        
        for task in self.config.tasks:
            task_type = task['type']
            if task_type in self.plugins:
                try:
                    self.plugins[task_type].backup(task)
                except Exception as e:
                    self.logger.error(f"Task {task_type} failed: {str(e)}")
            else:
                self.logger.error(f"No plugin found for task type: {task_type}")

        self._cleanup_old_backups()

def check_dependencies(config):
    """根据配置文件检查必要的命令行工具"""
    required_commands = {
        'tar': 'tar command',
        'docker': 'Docker command line'
    }
    
    # 遍历任务检查是否需要额外的依赖
    for task in config.tasks:
        task_type = task['type']
        is_docker = task.get('docker', {}).get('is-docker', False)
        
        # 只有非docker任务才需要检查数据库工具
        if not is_docker:
            if task_type == 'mongodb':
                required_commands['mongodump'] = 'MongoDB tools'
            elif task_type == 'mysql':
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
            logger.info(f"Found {len(config.tasks)} tasks")
            
            backup_system = BackupSystem(args.file)
            backup_system.run()
        elif args.test:
            config = ConfigManager(args.test, logger)
            check_dependencies(config)
            logger.info(f"Config file validated successfully: {args.test}")
            logger.info(f"Backup root: {config.backup_root}")
            logger.info(f"Backup keep days: {config.backup_keep_days}")
            logger.info(f"Found {len(config.tasks)} tasks")
            
            # 显示每个任务的基本信息
            for i, task in enumerate(config.tasks, 1):
                logger.info(f"Task {i}: type={task['type']}, docker={'is-docker' in task.get('docker', {})}")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
