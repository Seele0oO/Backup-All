from datetime import datetime
from pathlib import Path
from typing import Set
import tarfile
import fnmatch
import os

from core.backup_base import BackupPlugin
from core.config import FolderConfig

class FolderBackup(BackupPlugin):
    def get_type(self) -> str:
        return "folder"

    def backup(self, task_config: FolderConfig) -> bool:
        self.logger.info(f"Starting folder backup: {task_config.path}")

        try:
            if not task_config.path.exists():
                raise FileNotFoundError(f"Source path does not exist: {task_config.path}")

            backup_path = self._prepare_backup_path(task_config)
            exclude_patterns = set(task_config.exclude or [])
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            archive_path = backup_path / f"{task_config.path.name}-{timestamp}.tar.gz"

            self._create_backup_archive(task_config.path, archive_path, exclude_patterns)
            
            self.logger.info(f"Folder backup completed: {archive_path}")
            return True

        except Exception as e:
            self.logger.error(f"Folder backup failed: {str(e)}")
            return False

    def _create_backup_archive(self, source_path: Path, archive_path: Path, 
                             exclude_patterns: Set[str]) -> None:
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                parent_path = source_path.parent
                for root, dirs, files in os.walk(source_path):
                    relative_root = str(Path(root).relative_to(parent_path))
                    
                    # 过滤目录
                    dirs[:] = [
                        d for d in dirs 
                        if not any(fnmatch.fnmatch(str(Path(relative_root) / d), pattern)
                                 for pattern in exclude_patterns)
                    ]

                    # 添加文件
                    for file in files:
                        file_path = Path(root) / file
                        relative_path = str(file_path.relative_to(parent_path))
                        
                        if not any(fnmatch.fnmatch(relative_path, pattern)
                                 for pattern in exclude_patterns):
                            tar.add(file_path, arcname=relative_path)
                            self.logger.debug(f"Added file to archive: {relative_path}")

            self._verify_archive(archive_path)

        except Exception as e:
            if archive_path.exists():
                archive_path.unlink()
            raise Exception(f"Failed to create backup archive: {str(e)}")

    def _verify_archive(self, archive_path: Path) -> None:
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.getmembers()
        except Exception as e:
            raise Exception(f"Archive verification failed: {str(e)}")
