import datetime
import json
import os
import subprocess
import sys
import tarfile
import time

def mkdirIfNotExist(path):
    if not os.path.exists(path):
        os.makedirs(path)
        
def readJson():
    with open('config.json') as f:
        data = json.load(f)
        return data

def mysqlBackup(mysql):
    print("mysqlBackup")
    backup_base_path = globalSettings[0].get('backup_root')
    database_name = mysql.get('database')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backupPath = f"{backup_base_path}/mysql/{database_name}/{timestamp}.sql"
    mkdirIfNotExist(f"{backup_base_path}/mysql/{database_name}/")
    
    host = mysql.get('host')
    user = mysql.get('username')
    password = mysql.get('password')
    database = mysql.get('database')
    
    is_docker = mysql.get('docker').get("is-docker")
    
    if is_docker:
        print("docker")
        container = mysql.get('docker').get("container_name")
        cmd = f"docker exec -i {container} mysqldump -h {host} -u {user} -p{password} {database} > {backupPath}"
        subprocess.run(cmd, shell=True)
    else:
        print("no docker")
        cmd = f"mysqldump -h {host} -u {user} -p{password} {database} > {backupPath}"
        subprocess.run(cmd, shell=True)

    print(mysql)
    print(backupPath)
    print(cmd)


def mongodbBackup(mongodb):
    print("mongodbBackup")
    backup_base_path = globalSettings[0].get('backup_root')
    database_name = mongodb.get('database')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backupPath = f"{backup_base_path}/mongodb/{database_name}/{timestamp}.sql"
    mkdirIfNotExist(f"{backup_base_path}/mongodb/{database_name}/")
    
    host = mongodb.get('host')
    user = mongodb.get('username')
    password = mongodb.get('password')
    database = mongodb.get('database')
    
    is_docker = mongodb.get('docker').get("is-docker")
    
    if is_docker:
        print("docker")
        container = mongodb.get('docker').get("container_name")
        cmd = f"docker exec -i {container} mongodump --host {host} --db {database} --username {user} --password {password} --out {backupPath}"
    else:
        print("no docker")
        cmd = f"mongodump --host {host} --db {database} --username {user} --password {password} --out {backupPath}"
    
    print(mongodb)
    print(backupPath)
    print(cmd)

def stop_docker_service():
    try:
        # 停止Docker服务
        subprocess.run(['sudo', 'systemctl', 'stop', 'docker.service'], check=True)
        # 停止Docker socket
        subprocess.run(['sudo', 'systemctl', 'stop', 'docker.socket'], check=True)
        print("Docker服务和Socket已成功停止。")
    except subprocess.CalledProcessError:
        print("停止Docker服务或Socket失败。", file=sys.stderr)
    except Exception as e:
        print(f"发生错误：{e}", file=sys.stderr)

def start_docker_service():
    try:
        # 启动Docker socket
        subprocess.run(['sudo', 'systemctl', 'start', 'docker.socket'], check=True)
        # 启动Docker服务
        subprocess.run(['sudo', 'systemctl', 'start', 'docker.service'], check=True)
        print("Docker服务和Socket已成功启动。")
    except subprocess.CalledProcessError:
        print("启动Docker服务或Socket失败。", file=sys.stderr)
    except Exception as e:
        print(f"发生错误：{e}", file=sys.stderr)

def validate_tar_gz(file_path):
    try:
        with tarfile.open(file_path, 'r:gz') as tar:
            tar.getmembers()
        print(f"{file_path} is a valid tar.gz file.")
        return True
    except tarfile.ReadError:
        print(f"{file_path} is not a valid tar.gz file.")
        return False


def volumeBackup(volume):
    print("volumeBackup")
    volume_name = volume.get('docker').get('volume_name')
    backup_base_path = globalSettings[0].get('backup_root')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backupPath = f"{backup_base_path}/volume/{volume_name}/{timestamp}.tgz"
    dockerRoot = globalSettings[0].get('docker_root')
    mkdirIfNotExist(f"{backup_base_path}/volume/{volume_name}/")

    cmd=f"tar -czvf {backupPath} {dockerRoot}/volumes/{volume_name}"
    subprocess.run(cmd, shell=True)
    print(f"Backup volume {volume_name} to {backupPath}")
    if validate_tar_gz(f"{backupPath}"):
        print("Backup successful")
    else:
        print(f"volume {volume_name} Backup failed")

def folderBackup(folder):
    print("folderBackup")
    print(folder.get('path'))
    path=folder.get('path')
    backup_base_path = globalSettings[0].get('backup_root')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path_name = path.replace("/", "_")[1:]
    backupPath = f"{backup_base_path}/folder/{path_name}/{timestamp}.tgz"
    mkdirIfNotExist(f"{backup_base_path}/folder/{path_name}/")
    
    cmd=f"tar -czvf {backupPath} {path}"
    subprocess.run(cmd, shell=True)
    print(f"Backup folder {path} to {backupPath}")
    if validate_tar_gz(f"{backupPath}"):
        print("Backup successful")
    else:
        print(f"folder {path} Backup failed")
    

def taskParseconfig(task):
    task_type = task.get('type')
    if task_type == "mysql":
        print(task.get('database'))
        mysqlBackup(task)
    elif task_type == "mongodb":
        print(task.get('database'))
        mongodbBackup(task)
    elif task_type == "volume":
        print(task.get('docker').get('container_name'))
        volumeBackup(task)
    elif task_type == "folder":
        print(task.get('path'))
        folderBackup(task)
    else:
        print(task)
        print("task type not found")
        sys.exit(1)

def mainLoop():
    data = readJson()
    # read globalSettings Configuration
    print(data['settings'])
    global globalSettings
    globalSettings = data['settings']
    # read tasks Configuration
    print(data['tasks'])
    tasks = data['tasks']
    # for task in tasks:
    #     taskParseconfig(task)
    # 取出非docker的任务
    for task in tasks:
        if task.get('type') != "volume":
            taskParseconfig(task)
        else:
            pass
    # 取出docker的任务
    stop_docker_service(max_attempts=3)
    for task in tasks:
        if task.get('type') == "volume":
            taskParseconfig(task)
        else:
            pass
    start_docker_service(max_attempts=3)

if __name__ == "__main__":
    mainLoop()