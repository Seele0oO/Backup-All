import datetime
import json
import os
import shutil
import subprocess
import tarfile
import logging

class BackupManager:
    """备份管理器类，用于备份数据库和文件夹/卷。
    """
    def __init__(self, config_file='config.json'):
        """_summary_

        Args:
            config_file (str, optional): _description_. Defaults to 'config.json'.
        """
        self.config = self.read_json(config_file)
        # 从列表中获取第一个设置字典
        self.backup_root = self.config['settings'][0]['backup_root']
        self.docker_root = self.config['settings'][0]['docker_root']
        self.backup_keep_days     = self.config['settings'][0]['backup_keep_days']
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Configuration loaded: {self.config}")

    def read_json(self, file_path):
        """_summary_

        Args:
            file_path (_type_): _description_

        Returns:
            _type_: _description_
        """
        with open(file_path, 'r') as file:
            return json.load(file)

    def mkdir_if_not_exist(self, path):
        """_summary_

        Args:
            path (_type_): _description_
        """
        os.makedirs(path, exist_ok=True)

    def stop_docker_service(self):
        """_summary_

        Raises:
            RuntimeError: _description_
        """
        try:
            subprocess.run(['sudo', 'systemctl', 'stop', 'docker.service'], check=True)
            subprocess.run(['sudo', 'systemctl', 'stop', 'docker.socket'], check=True)
            logging.info("Docker服务和Socket已成功停止。")
        except subprocess.CalledProcessError as e:
            logging.error("停止Docker服务或Socket失败。")
            raise RuntimeError("Failed to stop Docker services") from e
        except Exception as e:
            logging.error(f"发生错误：{e}")
            raise

    def start_docker_service(self):
        """_summary_

        Raises:
            RuntimeError: _description_
        """
        try:
            subprocess.run(['sudo', 'systemctl', 'start', 'docker.socket'], check=True)
            subprocess.run(['sudo', 'systemctl', 'start', 'docker.service'], check=True)
            logging.info("Docker服务和Socket已成功启动。")
        except subprocess.CalledProcessError as e:
            logging.error("启动Docker服务或Socket失败。")
            raise RuntimeError("Failed to start Docker services") from e
        except Exception as e:
            logging.error(f"发生错误：{e}")
            raise

    def get_docker_container_id(self, container_name):
        """_summary_

        Args:
            container_name (_type_): _description_

        Raises:
            RuntimeError: _description_

        Returns:
            _type_: _description_
        """
        try:
            result = subprocess.run(['docker', 'ps', '-qf', f'name=^/{container_name}'], stdout=subprocess.PIPE, check=True, text=True)
            container_id = result.stdout.strip()
            logging.info(f"获取容器ID成功：{container_id}")
            return container_id
        except subprocess.CalledProcessError as e:
            logging.error(f"获取容器ID失败。")
            raise RuntimeError(f"Failed to get Docker container ID for {container_name}") from e
        except Exception as e:
            logging.error(f"发生错误：{e}")
            raise

    def backup_database(self, database_info, db_type='mysql'):
        """_summary_

        Args:
            database_info (_type_): _description_
            db_type (str, optional): _description_. Defaults to 'mysql'.
        """
        backup_base_path = f"{self.backup_root}/{db_type}/{database_info['database']}"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.mkdir_if_not_exist(backup_base_path)

        host = database_info['host']
        port = database_info['port']
        user = database_info.get('username', '')
        password = database_info.get('password', '')
        database = database_info['database']
        is_docker = database_info.get('docker', {}).get("is-docker", False)

        if db_type == 'mysql':
            backup_path = f"{backup_base_path}/{timestamp}.sql"
            dump_cmd = f"mysqldump -h {host} -u {user} -p{password} --port {port} {database} > {backup_path}"
        elif db_type == 'mongodb':
            temp_dir = f"/tmp/{database}_{timestamp}"
            backup_path = f"{backup_base_path}/{timestamp}.tgz"
            self.mkdir_if_not_exist(temp_dir)
            dump_cmd = f"mongodump --host {host} --port {port} --db {database} --out {temp_dir}"
            if user and password:
                dump_cmd += f" --username {user} --password {password}"
        
        if is_docker:
            container = self.get_docker_container_id(database_info['docker']['container_name'])
            docker_cmd = f"docker exec -i {container}"
            cmd = f"{docker_cmd} {dump_cmd}"
        else:
            cmd = dump_cmd

        subprocess.run(cmd, shell=True)
        
        if db_type == 'mongodb':
            if is_docker:
                # 将MongoDB导出的文件夹复制到主机
                copy_cmd = f"docker cp {container}:{temp_dir} {self.backup_root}/{db_type}/temp"
                subprocess.run(copy_cmd, shell=True)
                # 压缩MongoDB导出的文件夹
                # tar_cmd = f"tar -czvf {backup_path} -C {self.backup_root}/{db_type}/temp {database}"
                # subprocess.run(tar_cmd, shell=True)
                # 使用tarfile库压缩
                backup_root = f"{self.backup_root}/{db_type}/temp/{database}"
                with tarfile.open(backup_path, "w:gz") as tar:
                    for root, dirs, files in os.walk(backup_root):
                        for file in files:
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, backup_root)
                            tar.add(full_path, arcname=relative_path)
                # 检查压缩文件是否有效
                if not self.validate_tar_gz(backup_path):
                    logging.error(f"Backup of {db_type} database {database} failed.")
                    return
                # 删除MongoDB导出的文件夹
                shutil.rmtree(f"{self.backup_root}/{db_type}/temp")
            else:
                # 压缩MongoDB导出的文件夹
                # tar_cmd = f"tar -czvf {backup_path} -C {temp_dir} ."
                # subprocess.run(tar_cmd, shell=True)
                # 使用tarfile库压缩
                with tarfile.open(backup_path, "w:gz") as tar:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, temp_dir)
                            tar.add(full_path, arcname=relative_path, filter='data')
                # 检查压缩文件是否有效
                if not self.validate_tar_gz(backup_path):
                    logging.error(f"Backup of {db_type} database {database} failed.")
                    return
                # 清理临时文件夹
                shutil.rmtree(temp_dir)

        logging.info(f"Backup of {db_type} database {database} completed successfully at {backup_path}.")

    def backup_volume_or_folder(self, item, item_type='folder'):
        """_summary_

        Args:
            item (_type_): _description_
            item_type (str, optional): _description_. Defaults to 'folder'.
        """
        # 检查必需的键是否存在
        if 'docker' not in item and item_type == 'volume':
            logging.error(f"Volume item missing 'docker' key: {item}")
            return
        elif 'path' not in item and item_type == 'folder':
            logging.error(f"Folder item missing 'path' key: {item}")
            return

        item_name = item['docker']['volume_name'] if item_type == 'volume' else item['path'].replace('/', '_')[1:]
        backup_base_path = f"{self.backup_root}/{item_type}/{item_name}"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = f"{backup_base_path}/{timestamp}.tgz"
        self.mkdir_if_not_exist(backup_base_path)

        if item_type == 'volume':
            source_path = f"{self.docker_root}/volumes/{item['docker']['volume_name']}"
        else:
            source_path = item['path']

        # cmd = f"tar -czvf {backup_path} {source_path}"
        # subprocess.run(cmd, shell=True)
        with tarfile.open(backup_path, "w:gz") as tar:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, source_path)
                    tar.add(full_path, arcname=relative_path)
        # 检查压缩文件是否
        if self.validate_tar_gz(backup_path):
            logging.info(f"Backup of {item_type} {item_name} completed successfully.")
        else:
            logging.error(f"{item_type} {item_name} backup failed.")

    def validate_tar_gz(self, file_path):
        """_summary_

        Args:
            file_path (_type_): _description_

        Returns:
            _type_: _description_
        """
        try:
            with tarfile.open(file_path, 'r:gz') as tar:
                tar.getmembers()
            return True
        except tarfile.ReadError:
            return False

    def parse_and_execute_task(self, task):
        """_summary_

        Args:
            task (_type_): _description_

        Raises:
            ValueError: _description_
        """
        task_type = task.get('type')
        if task_type in ['mysql', 'mongodb']:
            self.backup_database(task, db_type=task_type)
        elif task_type in ['volume', 'folder']:
            self.backup_volume_or_folder(task, item_type=task_type)
        else:
            logging.error(f"Unsupported task type: {task_type}")
            raise ValueError("Unsupported task type")

    def main_loop(self):
        """_summary_
        """
        tasks = self.config['tasks']
        try:
            # self.stop_docker_service()
            for task in tasks:
                if task.get('type') != "volume":
                    self.parse_and_execute_task(task)
            for task in tasks:
                if task.get('type') == "volume":
                    self.parse_and_execute_task(task)
            # self.start_docker_service()
        except Exception as e:
            logging.error(f"An error occurred during the backup process: {e}")
        finally:
            self.remove_old_backups()

    def remove_old_backups(self):
        """_summary_
        """
        # cmd = f"find {self.backup_root} -mmin +2 -name '*.*' -exec rm -rf {{}} \;"
        # 删除{backup_keep_days}天前的备份
        cmd = f"find {self.backup_root} -mtime +{self.backup_keep_days} -name '*.*' -exec rm -rf {{}} \;"
        subprocess.run(cmd, shell=True)
        logging.info(f"Old backups removed from {self.backup_root}.")

if __name__ == "__main__":
    backup_manager = BackupManager()
    backup_manager.main_loop()
