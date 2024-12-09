from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import subprocess
import tarfile

from core.backup_base import BackupPlugin
from utils.docker_helper import DockerHelper


class MongoDBBackup(BackupPlugin):
    """MongoDB 备份插件"""

    def __init__(self, logger, backup_root: Path):
        super().__init__(logger, backup_root)
        self.docker_helper = DockerHelper()

    def get_type(self) -> str:
        return "mongodb"

    def backup(self, task_config: Dict) -> bool:
        """执行 MongoDB 备份

        Args:
            task_config: 任务配置字典，包含连接信息和备份选项

        Returns:
            bool: 备份是否成功
        """
        self.logger.info(f"Starting MongoDB backup: {task_config['database']}")

        try:
            backup_path = self._prepare_backup_path(task_config)
            if task_config['docker']['is-docker']:
                success = self._docker_backup(task_config, backup_path)
            else:
                success = self._local_backup(task_config, backup_path)
            
            if success:
                self.logger.info(f"MongoDB backup completed: {backup_path}")
            return success

        except Exception as e:
            self.logger.error(f"MongoDB backup failed: {str(e)}")
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

    def _build_mongodump_cmd(self, task_config: Dict, output_path: Path) -> list:
        """构建 mongodump 命令"""
        cmd = [
            'mongodump',
            '--host', 'localhost',  # 在容器内使用 localhost
            '--port', '27017',      # 使用容器内部端口
            '--db', task_config['database'],
            '--out', str(output_path)
        ]

        # 只有当用户名和密码都存在时才添加认证信息
        if task_config.get('username') and task_config.get('password'):
            cmd.extend(['--username', task_config['username']])
            cmd.extend(['--password', task_config['password']])

        if 'excludeCollection' in task_config:
            for coll in task_config['excludeCollection']:
                cmd.extend(['--excludeCollection', coll])

        return cmd

    def _local_backup(self, task_config: Dict, backup_path: Path) -> bool:
        """执行本地备份"""
        temp_path = backup_path / 'temp'
        self.create_folder(temp_path)

        try:
            # 执行 mongodump
            cmd = self._build_mongodump_cmd(task_config, temp_path)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"mongodump failed: {result.stderr}")

            # 压缩备份
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            archive_name = f"{task_config['database']}-{timestamp}.tar.gz"
            archive_path = backup_path / archive_name

            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(temp_path, arcname=temp_path.name)

            # 清理临时文件
            subprocess.run(['rm', '-rf', str(temp_path)])
            return True

        except Exception as e:
            self.logger.error(f"Local backup failed: {str(e)}")
            return False

    def _docker_backup(self, task_config: Dict, backup_path: Path) -> bool:
        """在 Docker 容器中执行备份"""
        try:
            container = self.docker_helper.get_container(task_config['docker']['container_name'])
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # 在容器中创建临时目录
            container_temp = f"/tmp/mongodb_backup_{timestamp}"
            result = container.exec_run(f"mkdir -p {container_temp}")
            if result[0] != 0:
                raise Exception("Failed to create temp directory in container")

            # 执行 mongodump
            cmd = self._build_mongodump_cmd(task_config, Path(container_temp))
            result = container.exec_run(' '.join(cmd))
            if result[0] != 0:
                raise Exception(f"mongodump failed in container: {result[1]}")

            # 压缩备份
            archive_name = f"{task_config['database']}-{timestamp}.tar.gz"
            tar_cmd = f"tar -czf /tmp/{archive_name} -C {container_temp} ."
            result = container.exec_run(tar_cmd)
            if result[0] != 0:
                raise Exception(f"Tar failed in container: {result[1]}")

            # 从容器复制到主机
            with open(backup_path / archive_name, 'wb') as f:
                bits, _ = container.get_archive(f"/tmp/{archive_name}")
                for chunk in bits:
                    f.write(chunk)

            # 清理容器中的临时文件
            container.exec_run(f"rm -rf {container_temp} /tmp/{archive_name}")
            return True

        except Exception as e:
            self.logger.error(f"Docker backup failed: {str(e)}")
            return False
