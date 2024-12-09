from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import subprocess
import gzip

from core.backup_base import BackupPlugin
from utils.docker_helper import DockerHelper


class MySQLBackup(BackupPlugin):
    """MySQL 备份插件"""

    def __init__(self, logger, backup_root: Path):
        super().__init__(logger, backup_root)
        self.docker_helper = DockerHelper()

    def get_type(self) -> str:
        return "mysql"

    def backup(self, task_config: Dict) -> bool:
        """执行 MySQL 备份

        Args:
            task_config: 任务配置字典，包含连接信息和备份选项

        Returns:
            bool: 备份是否成功
        """
        self.logger.info(f"Starting MySQL backup: {task_config['database']}")

        try:
            backup_path = self._prepare_backup_path(task_config)
            if task_config['docker']['is-docker']:
                success = self._docker_backup(task_config, backup_path)
            else:
                success = self._local_backup(task_config, backup_path)

            if success:
                self.logger.info(f"MySQL backup completed: {backup_path}")
            return success

        except Exception as e:
            self.logger.error(f"MySQL backup failed: {str(e)}")
            return False

    def _prepare_backup_path(self, task_config: Dict) -> Path:
        """准备备份目录并返回路径
        
        命名模式：
        数据库：{type}_{container_name}_{database}
        文件夹：folder_{folder_name}
        卷：volume_{volume_name}
        """
        if task_config['type'] == 'mongodb':
            backup_name = f"mongodb_{task_config['docker']['container_name']}_{task_config['database']}"
        
        elif task_config['type'] == 'mysql':
            backup_name = f"mysql_{task_config['docker']['container_name']}_{task_config['database']}"
        
        elif task_config['type'] == 'folder':
            backup_name = f"folder_{Path(task_config['path']).name}"
        
        elif task_config['type'] == 'volume':
            backup_name = f"volume_{task_config['docker']['volume_name']}"
        
        backup_path = self.backup_root / backup_name
        self.create_folder(backup_path)
        return backup_path

    def _build_mysqldump_cmd(self, task_config: Dict) -> list:
        """构建 mysqldump 命令"""
        return [
            'mysqldump',
            '-h', task_config['host'],
            '-P', str(task_config['port']),
            '-u', task_config['username'],
            f"-p{task_config['password']}",
            task_config['database']
        ]

    def _local_backup(self, task_config: Dict, backup_path: Path) -> bool:
        """执行本地备份"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            output_file = backup_path / f"{task_config['database']}-{timestamp}.sql.gz"

            # 执行 mysqldump 并使用 gzip 压缩
            with gzip.open(output_file, 'wb') as f:
                mysqldump_process = subprocess.Popen(
                    self._build_mysqldump_cmd(task_config),
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

    def _docker_backup(self, task_config: Dict, backup_path: Path) -> bool:
        """在 Docker 容器中执行备份"""
        try:
            container = self.docker_helper.get_container(task_config['docker']['container_name'])
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            temp_file = f"/tmp/{task_config['database']}-{timestamp}.sql.gz"
            output_file = backup_path / f"{task_config['database']}-{timestamp}.sql.gz"

            # 构建 mysqldump 命令
            mysqldump_cmd = (
                f"mysqldump -h {task_config['host']} "
                f"-P {task_config['port']} "
                f"-u {task_config['username']} "
                f"-p{task_config['password']} "
                f"{task_config['database']} | gzip > {temp_file}"
            )
            
            # 使用 sh -c 执行完整命令
            result = container.exec_run(
                cmd=['sh', '-c', mysqldump_cmd],
                environment={"MYSQL_PWD": task_config['password']}  # 使用环境变量传递密码
            )
            
            if result.exit_code != 0:
                raise Exception(f"mysqldump failed in container: {result.output}")

            # 从容器复制到主机
            with open(output_file, 'wb') as f:
                bits, _ = container.get_archive(temp_file)
                for chunk in bits:
                    f.write(chunk)

            # 清理临时文件
            container.exec_run(f"rm -f {temp_file}")
            return True

        except Exception as e:
            self.logger.error(f"Docker backup failed: {str(e)}")
            return False
