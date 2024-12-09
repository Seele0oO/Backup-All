from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import tarfile

from core.backup_base import BackupPlugin


class FolderBackup(BackupPlugin):
    """文件夹备份插件"""

    def get_type(self) -> str:
        return "folder"

    def backup(self, task_config: Dict) -> bool:
        """执行文件夹备份

        Args:
            task_config: 任务配置字典，包含路径和排除选项

        Returns:
            bool: 备份是否成功
        """
        self.logger.info(f"Starting folder backup: {task_config['path']}")

        try:
            source_path = Path(task_config['path'])
            excludes = set(task_config.get('exclude', []))
            
            # 准备备份目录
            backup_path = self.backup_root / f"folder_{source_path.name}"
            self.create_folder(backup_path)
            
            # 创建备份文件
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            archive_path = backup_path / f"{source_path.name}-{timestamp}.tar.gz"

            def filter_func(tarinfo):
                """过滤要排除的文件"""
                if any(exclude in tarinfo.name for exclude in excludes):
                    return None
                return tarinfo

            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(source_path, arcname=source_path.name, filter=filter_func)

            self.logger.info(f"Folder backup completed: {archive_path}")
            return True

        except Exception as e:
            self.logger.error(f"Folder backup failed: {str(e)}")
            return False