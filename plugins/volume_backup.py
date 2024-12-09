from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from core.backup_base import BackupPlugin
from utils.docker_helper import DockerHelper


class VolumeBackup(BackupPlugin):
    """Docker 卷备份插件"""

    def __init__(self, logger, backup_root: Path):
        super().__init__(logger, backup_root)
        self.docker_helper = DockerHelper()

    def get_type(self) -> str:
        return "volume"

    def backup(self, task_config: Dict) -> bool:
        """执行 Docker 卷备份

        Args:
            task_config: 任务配置字典，包含卷名称

        Returns:
            bool: 备份是否成功
        """
        self.logger.info(f"Starting volume backup: {task_config['docker']['volume_name']}")

        try:
            volume_name = task_config['docker']['volume_name']
            backup_path = self.backup_root / f"volume_{volume_name}"
            self.create_folder(backup_path)

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            archive_name = f"{volume_name}-{timestamp}.tar"
            output_file = backup_path / archive_name

            # 使用临时容器备份卷
            container = self.docker_helper.client.containers.run(
                "alpine",
                f"tar cvf /backup/{archive_name} /volume",
                volumes={
                    volume_name: {"bind": "/volume", "mode": "ro"},
                    str(backup_path): {"bind": "/backup", "mode": "rw"}
                },
                remove=True
            )

            if output_file.exists():
                self.logger.info(f"Volume backup completed: {output_file}")
                return True
            else:
                self.logger.error(f"Backup file not created: {output_file}")
                return False

        except Exception as e:
            self.logger.error(f"Volume backup failed: {str(e)}")
            return False
