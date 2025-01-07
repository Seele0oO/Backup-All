from datetime import datetime
from pathlib import Path

from core.backup_base import BackupPlugin
from core.config import VolumeConfig
from utils.docker_helper import DockerHelper

class VolumeBackup(BackupPlugin):
    def __init__(self, logger, backup_root: Path):
        super().__init__(logger, backup_root)
        self.docker_helper = DockerHelper()

    def get_type(self) -> str:
        return "volume"

    def backup(self, task_config: VolumeConfig) -> bool:
        self.logger.info(f"Starting volume backup: {task_config.name}")

        try:
            backup_path = self._prepare_backup_path(task_config)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            archive_name = f"{task_config.name}-{timestamp}.tar"
            output_file = backup_path / archive_name

            container = self.docker_helper.client.containers.run(
                "registry.cn-hangzhou.aliyuncs.com/cqtech/busybox:latest",
                f"tar cvf /backup/{archive_name} /volume",
                volumes={
                    task_config.name: {"bind": "/volume", "mode": "ro"},
                    str(backup_path): {"bind": "/backup", "mode": "rw"}
                },
                remove=True
            )

            if output_file.exists():
                self.logger.info(f"Volume backup completed: {output_file}")
                return True
            else:
                raise Exception(f"Backup file not created: {output_file}")

        except Exception as e:
            self.logger.error(f"Volume backup failed: {str(e)}")
            return False
