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
        """初始化备份管理器。

        Args:
            config_file (str, optional): 配置文件的路径，默认为'config.json'.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        try:
            self.config = self.read_json(config_file)
            logging.info(f"成功加载配置文件: {config_file}")
        except FileNotFoundError as e:
            logging.error(f"配置文件{config_file}未找到。")
            raise FileNotFoundError(f"Configuration file {config_file} not found") from e
            SystemExit(1)
        except Exception as e:
            logging.error(f"加载配置文件时发生错误：{e}")
            raise SystemExit(1)
        
        # 从列表中获取第一个设置字典
        self.backup_root = self.config['settings'][0]['backup_root']
        self.docker_root = self.config['settings'][0]['docker_root']
        self.backup_keep_days     = self.config['settings'][0]['backup_keep_days']
        logging.basicConfig(level=logging.INFO)
        logging.info(f"配置文件已载入: {self.config}")

    def read_json(self, file_path):
        """从指定路径读取JSON文件。

        Args:
            file_path (str): JSON文件的路径。

        Returns:
            dict: JSON文件内容。
        """
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                logging.info(f"JSON文件{file_path}读取成功。")
                return data
        except json.JSONDecodeError as e:
            logging.error(f"解析JSON文件{file_path}时出错: {e}")
            raise
        except Exception as e:
            logging.error(f"打开JSON文件{file_path}时出错: {e}")
            raise

    def mkdir_if_not_exist(self, path):
        """如果指定路径不存在，则创建目录。

        Args:
            path (str): 需要创建的目录路径。
        """
        try:
            os.makedirs(path, exist_ok=True)
            logging.info(f"目录{path}已创建或已存在。")
        except Exception as e:
            logging.error(f"创建目录{path}失败：{e}")
            raise

    def stop_docker_service(self):
        """停止Docker服务和相关的Socket。"""

        try:
            subprocess.run(['sudo', 'systemctl', 'stop', 'docker.service'], check=True)
            subprocess.run(['sudo', 'systemctl', 'stop', 'docker.socket'], check=True)
            logging.info("Docker服务和Socket已成功停止。")
        except subprocess.CalledProcessError as e:
            logging.error("停止Docker服务或Socket失败：", str(e))
            raise RuntimeError("Failed to stop Docker services") from e
        except Exception as e:
            logging.error(f"停止Docker服务时发生错误：{e}")
            raise

    def start_docker_service(self):
        """启动Docker服务和相关的Socket。"""
        try:
            subprocess.run(['sudo', 'systemctl', 'start', 'docker.socket'], check=True)
            subprocess.run(['sudo', 'systemctl', 'start', 'docker.service'], check=True)
            logging.info("Docker服务和Socket已成功启动。")
        except subprocess.CalledProcessError as e:
            logging.error("启动Docker服务或Socket失败：", str(e))
            raise RuntimeError("Failed to start Docker services") from e
        except Exception as e:
            logging.error(f"启动Docker服务时发生错误：{e}")
            raise

    def get_docker_container_id(self, container_name):
        """根据容器名获取Docker容器ID。

        Args:
            container_name (str): Docker容器名。

        Returns:
            str: Docker容器ID。

        Raises:
            RuntimeError: 获取容器ID失败。
        """
        try:
            result = subprocess.run(['docker', 'ps', '-qf', f'name=^/{container_name}'], stdout=subprocess.PIPE, check=True, text=True)
            container_id = result.stdout.strip()
            if container_id:
                logging.info(f"获取容器{container_name}的ID成功：{container_id}")
                return container_id
            else:
                logging.warning(f"未找到名为{container_name}的容器。")
                raise RuntimeError(f"No container found with name {container_name}")
        except subprocess.CalledProcessError as e:
            logging.error(f"获取容器{container_name}的ID失败：{e}")
            raise RuntimeError(f"Failed to get Docker container ID for {container_name}") from e
        except Exception as e:
            logging.error(f"获取容器ID时发生错误：{e}")
            raise

    def backup_database(self, database_info, db_type):
        """备份指定数据库。

        Args:
            database_info (dict): 数据库信息，包括主机、端口等。
            db_type (str, optional): 数据库类型。
        """
        backup_base_path = f"{self.backup_root}/{db_type}/{database_info['database']}"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.mkdir_if_not_exist(backup_base_path)

        logging.info(f"开始备份 {db_type} 数据库：{database_info['database']}")

        host = database_info['host']
        port = database_info['port']
        user = database_info.get('username', '')
        password = database_info.get('password', '')
        database = database_info['database']
        is_docker = database_info.get('docker', {}).get("is-docker", False)
        
        logging.info(f"数据库信息：{database_info}")

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

        logging.info(f"Dump command: {dump_cmd}")
        
        if is_docker:
            container = self.get_docker_container_id(database_info['docker']['container_name'])
            docker_cmd = f"docker exec -i {container}"
            cmd = f"{docker_cmd} {dump_cmd}"
        else:
            cmd = dump_cmd
        
        logging.info(f"Backup command: {cmd}")

        subprocess.run(cmd, shell=True)
        
        if db_type == 'mongodb':
            if is_docker:
                # 将MongoDB导出的文件夹复制到主机
                copy_cmd = f"docker cp {container}:{temp_dir} {self.backup_root}/{db_type}/temp"
                logging.info(f"Copying MongoDB dump from container to host: {copy_cmd}")
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
                    logging.error(f"类型为 {db_type} 的 database {database} 备份失败.")
                    return
                # 删除MongoDB导出的文件夹
                shutil.rmtree(f"{self.backup_root}/{db_type}/temp")
                logging.info(f"MongoDB dump from container to host completed successfully.")
            else:
                # 压缩MongoDB导出的文件夹
                # tar_cmd = f"tar -czvf {backup_path} -C {temp_dir} ."
                # subprocess.run(tar_cmd, shell=True)
                # 使用tarfile库压缩
                logging.info(f"Compressing MongoDB dump from host: {temp_dir}")
                with tarfile.open(backup_path, "w:gz") as tar:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, temp_dir)
                            tar.add(full_path, arcname=relative_path)
                # 检查压缩文件是否有效
                if not self.validate_tar_gz(backup_path):
                    logging.error(f"类型为 {db_type} 的 database {database} 备份失败.")
                    return
                else:
                    logging.info(f"类型为 {db_type} 的 database {database} 备份成功.")
                # 清理临时文件夹
                shutil.rmtree(temp_dir)

        # logging.info(f"Backup of {db_type} database {database} completed successfully at {backup_path}.")
        # zh-cn
        logging.info(f"{db_type} 数据库 {database} 的备份已成功完成,备份文件位于 {backup_path}。")

    def backup_volume_or_folder(self, item, item_type='folder'):
        """备份指定的文件夹或Docker卷。

        Args:
            item (dict): 包含备份项的详细信息。
            item_type (str, optional): 备份类型，'folder' 或 'volume'。
        """
        # 检查必需的键是否存在
        if 'docker' not in item and item_type == 'volume':
            logging.error(f"Volume 类型的项目缺少 'docker' 键: {item}")
            return
        elif 'path' not in item and item_type == 'folder':
            logging.error(f"Folder 类型的项目缺少 'path' 键: {item}")
            return

        item_name = item['docker']['volume_name'] if item_type == 'volume' else item['path'].replace('/', '_')[1:]
        backup_base_path = f"{self.backup_root}/{item_type}/{item_name}"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = f"{backup_base_path}/{timestamp}.tgz"
        self.mkdir_if_not_exist(backup_base_path)
        
        logging.info(f"开始备份 {item_type}：{item_name}")

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
        logging.info(f"备份 {item_type} {item_name} 完成。")
        # 检查压缩文件是否
        if self.validate_tar_gz(backup_path):
            logging.info(f"{item_type} {item_name} 的备份成功完成。")
        else:
            logging.error(f"{item_type} {item_name} 的备份失败。")

    def validate_tar_gz(self, file_path):
        """验证tar.gz文件的完整性。

        Args:
            file_path (str): tar.gz文件路径。

        Returns:
            bool: 验证结果。
        """
        try:
            with tarfile.open(file_path, 'r:gz') as tar:
                tar.getmembers()
            logging.info(f"文件 {file_path} 验证成功，无损坏。")
            return True
        except tarfile.ReadError:
            logging.error(f"文件 {file_path} 验证失败，文件可能已损坏。")
            return False

    def parse_and_execute_task(self, task):
        """解析并执行给定的备份任务。

        Args:
            task (dict): 任务详情。
        """
        try:
            task_type = task.get('type')
            if task_type not in ['mysql', 'mongodb', 'volume', 'folder']:
                logging.error(f"不支持的任务类型: {task_type}")
                raise ValueError("Unsupported task type")
            logging.info(f"执行任务类型：{task_type}")
            if task_type in ['mysql', 'mongodb']:
                self.backup_database(task, task_type)
            elif task_type in ['volume', 'folder']:
                self.backup_volume_or_folder(task, item_type=task_type)
        except Exception as e:
            logging.error(f"任务执行失败：{e}")


    def main_loop(self):
        """执行主循环，处理所有备份任务。"""
        logging.info("开始执行备份任务。")
        tasks = self.config['tasks']
        try:
            for task in tasks:
                self.parse_and_execute_task(task)
        except Exception as e:
            logging.error(f"在执行备份任务时发生错误：{e}")
        finally:
            self.remove_old_backups()
            logging.info("所有备份任务已完成。")

    def remove_old_backups(self):
        """_summary_
        """
        # cmd = f"find {self.backup_root} -mmin +2 -name '*.*' -exec rm -rf {{}} \;"
        # 删除{backup_keep_days}天前的备份
        cmd = f"find {self.backup_root} -mtime +{self.backup_keep_days} -name '*.*' -exec rm -rf {{}} \;"
        subprocess.run(cmd, shell=True)
        logging.info(f"旧的备份已经被移除 {self.backup_root}.")

if __name__ == "__main__":
    backup_manager = BackupManager()
    backup_manager.main_loop()
