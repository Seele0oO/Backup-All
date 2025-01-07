from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import subprocess
import tarfile

from core.backup_base import BackupPlugin
from core.config import DatabaseConfig
from utils.docker_helper import DockerHelper

class MongoDBBackup(BackupPlugin):
    def __init__(self, logger, backup_root: Path):
        super().__init__(logger, backup_root)
        self.docker_helper = DockerHelper()

    def get_type(self) -> str:
        return "mongodb"

    def backup(self, task_config: DatabaseConfig) -> bool:
        self.logger.info(f"Starting MongoDB backup: {task_config.database}")

        try:
            backup_path = self._prepare_backup_path(task_config)
            if task_config.docker.enabled:
                success = self._docker_backup(task_config, backup_path)
            else:
                success = self._local_backup(task_config, backup_path)
            
            if success:
                self.logger.info(f"MongoDB backup completed: {backup_path}")
            return success

        except Exception as e:
            self.logger.error(f"MongoDB backup failed: {str(e)}")
            return False

    def _build_mongodump_cmd(self, task_config: DatabaseConfig, output_path: Path) -> list:
        """构建 mongodump 命令"""
        cmd = [
            'mongodump',
            '--host', task_config.host,
            '--port', str(task_config.port),
            '--db', task_config.database,
            '--out', str(output_path)
        ]

        if task_config.auth:
            cmd.extend(['--username', task_config.auth.username])
            cmd.extend(['--password', task_config.auth.password])

        if task_config.exclude:
            for coll in task_config.exclude:
                cmd.extend(['--excludeCollection', coll])

        return cmd

    def _docker_backup(self, task_config: DatabaseConfig, backup_path: Path) -> bool:
        try:
            container = self.docker_helper.get_container(task_config.docker.container)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            container_temp = f"/tmp/mongodb_backup_{timestamp}"
            result = container.exec_run(f"mkdir -p {container_temp}")
            if result[0] != 0:
                raise Exception("Failed to create temp directory in container")

            # 构建 mongodump 命令
            cmd = self._build_mongodump_cmd(task_config, Path(container_temp))
            
            # 如果没有用户名和密码，删除相关参数
            if not task_config.auth.username:
                cmd = [arg for arg in cmd if arg not in ['-u', '--username', '-p', '--password']]
            
            result = container.exec_run(' '.join(cmd))
            if result[0] != 0:
                raise Exception(f"mongodump failed in container: {result[1]}")

            archive_name = f"{task_config.database}-{timestamp}.tar.gz"
            tar_cmd = f"tar -czf /tmp/{archive_name} -C {container_temp} ."
            result = container.exec_run(tar_cmd)
            if result[0] != 0:
                raise Exception(f"Tar failed in container: {result[1]}")

            with open(backup_path / archive_name, 'wb') as f:
                bits, _ = container.get_archive(f"/tmp/{archive_name}")
                for chunk in bits:
                    f.write(chunk)

            container.exec_run(f"rm -rf {container_temp} /tmp/{archive_name}")
            return True

        except Exception as e:
            self.logger.error(f"Docker backup failed: {str(e)}")
            return False

    def _local_backup(self, task_config: DatabaseConfig, backup_path: Path) -> bool:
        temp_path = backup_path / 'temp'
        self.create_folder(temp_path)

        try:
            cmd = self._build_mongodump_cmd(task_config, temp_path)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"mongodump failed: {result.stderr}")

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            archive_name = f"{task_config.database}-{timestamp}.tar.gz"
            archive_path = backup_path / archive_name

            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(temp_path, arcname=temp_path.name)

            subprocess.run(['rm', '-rf', str(temp_path)])
            return True

        except Exception as e:
            self.logger.error(f"Local backup failed: {str(e)}")
            return False