import datetime
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import logging

class BackupManager:
    def __init__(self, config_file='config.json'):
        self.config = self.read_json(config_file)
        # 从列表中获取第一个设置字典
        self.backup_root = self.config['settings'][0]['backup_root']
        self.docker_root = self.config['settings'][0]['docker_root']
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Configuration loaded: {self.config}")

    def read_json(self, file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    def mkdir_if_not_exist(self, path):
        os.makedirs(path, exist_ok=True)

    def stop_docker_service(self):
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
            # 压缩MongoDB导出的文件夹
            tar_cmd = f"tar -czvf {backup_path} -C {temp_dir} ."
            subprocess.run(tar_cmd, shell=True)
            # 清理临时文件夹
            shutil.rmtree(temp_dir)

        logging.info(f"Backup of {db_type} database {database} completed successfully at {backup_path}.")

    def backup_volume_or_folder(self, item, item_type='folder'):
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

        cmd = f"tar -czvf {backup_path} {source_path}"
        subprocess.run(cmd, shell=True)
        if self.validate_tar_gz(backup_path):
            logging.info(f"Backup of {item_type} {item_name} completed successfully.")
        else:
            logging.error(f"{item_type} {item_name} backup failed.")

    def validate_tar_gz(self, file_path):
        try:
            with tarfile.open(file_path, 'r:gz') as tar:
                tar.getmembers()
            return True
        except tarfile.ReadError:
            return False

    def parse_and_execute_task(self, task):
        task_type = task.get('type')
        if task_type in ['mysql', 'mongodb']:
            self.backup_database(task, db_type=task_type)
        elif task_type in ['volume', 'folder']:
            self.backup_volume_or_folder(task, item_type=task_type)
        else:
            logging.error(f"Unsupported task type: {task_type}")
            raise ValueError("Unsupported task type")

    def main_loop(self):
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
        cmd = f"find {self.backup_root} -mmin +2 -name '*.*' -exec rm -rf {{}} \;"
        subprocess.run(cmd, shell=True)
        logging.info(f"Old backups removed from {self.backup_root}.")

if __name__ == "__main__":
    backup_manager = BackupManager()
    backup_manager.main_loop()
