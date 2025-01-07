from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import subprocess
import gzip

from core.backup_base import BackupPlugin
from core.config import DatabaseConfig
from utils.docker_helper import DockerHelper

class MySQLBackup(BackupPlugin):
    def __init__(self, logger, backup_root: Path):
        super().__init__(logger, backup_root)
        self.docker_helper = DockerHelper()

    def get_type(self) -> str:
        return "mysql"

    def backup(self, task_config: DatabaseConfig) -> bool:
        self.logger.info(f"Starting MySQL backup: {task_config.database}")

        try:
            backup_path = self._prepare_backup_path(task_config)
            if task_config.docker.enabled:
                success = self._docker_backup(task_config, backup_path)
            else:
                success = self._local_backup(task_config, backup_path)

            if success:
                self.logger.info(f"MySQL backup completed: {backup_path}")
            return success

        except Exception as e:
            self.logger.error(f"MySQL backup failed: {str(e)}")
            return False

    def _docker_backup(self, task_config: DatabaseConfig, backup_path: Path) -> bool:
        try:
            container = self.docker_helper.get_container(task_config.docker.container)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            temp_file = f"/tmp/{task_config.database}-{timestamp}.sql.gz"
            output_file = backup_path / f"{task_config.database}-{timestamp}.sql.gz"

            # 使用环境变量传递密码
            mysqldump_cmd = (
                f"mysqldump -h {task_config.host} "
                f"-P {task_config.port} "
                f"-u {task_config.auth.username} "
                f"{task_config.database} | gzip > {temp_file}"
            )
            
            result = container.exec_run(
                cmd=['sh', '-c', mysqldump_cmd],
                environment={"MYSQL_PWD": task_config.auth.password}
            )
            
            if result.exit_code != 0:
                raise Exception(f"mysqldump failed in container: {result.output}")

            with open(output_file, 'wb') as f:
                bits, _ = container.get_archive(temp_file)
                for chunk in bits:
                    f.write(chunk)

            container.exec_run(f"rm -f {temp_file}")
            return True

        except Exception as e:
            self.logger.error(f"Docker backup failed: {str(e)}")
            return False

    def _local_backup(self, task_config: DatabaseConfig, backup_path: Path) -> bool:
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            output_file = backup_path / f"{task_config.database}-{timestamp}.sql.gz"

            with gzip.open(output_file, 'wb') as f:
                mysqldump_process = subprocess.Popen(
                    [
                        'mysqldump',
                        '-h', task_config.host,
                        '-P', str(task_config.port),
                        '-u', task_config.auth.username,
                        f"-p{task_config.auth.password}",
                        task_config.database
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = mysqldump_process.communicate()
                
                if mysqldump_process.returncode != 0:
                    raise Exception(f"mysqldump failed: {stderr.decode()}")
                
                f.write(stdout)

            return True

        except Exception as e:
            self.logger.error(f"Local backup failed: {str(e)}")
            return False