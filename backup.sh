#!/bin/bash

# 定义日志级别和日志文件
LOG_LEVELS="DEBUG INFO WARNING ERROR CRITICAL"
LOG_FILE="./my_script.log"

# 日志函数
log() {
  local level=$1 msg=$2
  local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

  if [[ "$level" == "ERROR" || "$level" == "CRITICAL" ]]; then
      echo "$timestamp [$level] $msg"
      echo "$timestamp [$level] $msg" >> "$LOG_FILE"
      exit 1
  else
      echo "$timestamp [$level] $msg"
      echo "$timestamp [$level] $msg" >> "$LOG_FILE"
  fi
}


# 检测是否安装必要软件，如 jq,tar ,如果没有安装，提示安装并退出脚本
check_software() {
    if ! command -v jq &> /dev/null; then
        log "ERROR" "jq is not installed, please install jq first"
    fi
    if ! command -v tar &> /dev/null; then
        log "ERROR" "tar is not installed, please install tar first"
    fi
}
# 读取全局配置文件
read_config() {
    if [ ! -f "config.json" ]; then
        log "ERROR" "config.json does not exist"
    fi
    backup_root=$(jq -r '.settings[0].backup_root' config.json)

    backup_keep_days=$(jq -r '.settings[0].backup_keep_days' config.json)

    docker_root=$(jq -r '.settings[0].docker_root' config.json)

    log "INFO" "backup_root: $backup_root"
    log "INFO" "backup_keep_days: $backup_keep_days"
    log "INFO" "docker_root: $docker_root"
}

read_tasks() {
    if [ ! -f "config.json" ]; then
        log "ERROR" "config.json does not exist"
    fi
    tasks=$(jq -c '.tasks[]' config.json)
    for task in $tasks; do
        read_a_config "$task"
    done
}

read_a_config() {
    local config_snippet=$1

    if jq -e . <<<"$config_snippet" >/dev/null; then
        task_type=$(jq -r '.type' <<<"$config_snippet")
        log "INFO" "There is a task config: $config_snippet"
        log "INFO" "task_type: $task_type"
        case "${task_type}" in
            mongodb)
                log "INFO" "task_type = mongodb"
                mongodb_task $config_snippet
            ;;
            mysql)
                log "INFO" "task_type = mysql"
            ;;
            folder)
                log "INFO" "task_type = folder"
            ;;
            volume)
                log "INFO" "task_type = volume"
            ;;
            *)
                log "ERROR" "Invalid task type: $task_type"
            ;;
        esac
        
    else
        log "ERROR" "Invalid task config: $config_snippet"
    fi
}

mongodb_task() {
    log "INFO" "mongodb_task"
    local config_snippet=$1
    local host
    local port
    local username
    local password
    local database

    host=$(jq -r '.host' <<<"$config_snippet")
    port=$(jq -r '.port' <<<"$config_snippet")
    username=$(jq -r '.username' <<<"$config_snippet")
    password=$(jq -r '.password' <<<"$config_snippet")
    database=$(jq -r '.database' <<<"$config_snippet")

    local is_docker
    is_docker=$(jq -r '.docker."is-docker"' <<<"$config_snippet")

    # check if variables are not empty
    if [ -z "$host" ] || [ -z "$port" ] || [ -z "$database" ]; then
        log "ERROR" "host, port, database are required"
    fi
    # INFO username and password are optional
    if [ -z "$username" ]|| [ -z "$password" ]; then
        log "INFO" "username & password is empty,but it's optional"
    fi
    local command
    local docker_command

    if $is_docker; then
        log "INFO" "is_docker = true"
        container_name=$(jq -r '.docker.container_name' <<<"$config_snippet")
        log "INFO" "container_name: $container_name"
        result=$(docker ps -q --filter "name=^/$container_name")
        if [ -n "$result" ]; then
            log "INFO" "Find a container named $container_name"
        else
            log "ERROR" "Can't find a container named $container_name"
        fi

        if [ $? -ne 0 ]; then
            log "ERROR" "docker exec failed, please check the container name"
        fi
        docker_command="docker exec -i $container_name"
    else
        log "INFO" "is_docker = false"
    fi

    # if without username & password
    if [ -z "$username" ]; then
        command=" mongodump --host $host --port $port --db $database"
    else
        command=" mongodump --host $host --port $port --username $username --password $password --db $database"
    fi

    # export to specified folder
    local out_command=""
    if $is_docker; then
        out_command="--out /tmp/$database && docker cp $container_name:/tmp/$database $backup_root/$database && docker exec -i $container_name sh -c 'rm -rf /tmp/$database'"
    else
        out_command="--out $backup_root/$database"
    fi

    # create tar && check tarfile is vaild &&remove origin folder
    local tar_filename
    tar_filename="$backup_root/$database-$(date +%Y%m%d%H%M%S).tar.gz"
    local tar_command="tar -zcvf $tar_filename $backup_root/$database"
    log "DEBUG" "tar_command: $tar_command"
    local rm_command="find $backup_root -name $database -type d -mtime +$backup_keep_days -exec rm -rf {} \;"
    log "DEBUG" "rm_command: $rm_command"
    local full_command="$docker_command $command $out_command && $tar_command && $rm_command"

    log "INFO" "full_command: $full_command"
}

mysql_task() {
    log "INFO" "mysql_task"
    local config_snippet=$1
    local host
    local port
    local username
    local password
    local database

    host=$(jq -r '.host' <<<"$config_snippet")
    port=$(jq -r '.port' <<<"$config_snippet")
    username=$(jq -r '.username' <<<"$config_snippet")
    password=$(jq -r '.password' <<<"$config_snippet")
    database=$(jq -r '.database' <<<"$config_snippet")

    local is_docker
    is_docker=$(jq -r '.docker."is-docker"' <<<"$config_snippet")
    
    local command
    local docker_command

    if $is_docker; then
        log "INFO" "is_docker = true"
        container_name=$(jq -r '.docker.container_name' <<<"$config_snippet")
        log "INFO" "container_name: $container_name"
        result=$(docker ps -q --filter "name=^/$container_name")
        if [ -n "$result" ]; then
            log "INFO" "Find a container named $container_name"
        else
            log "ERROR" "Can't find a container named $container_name"
        fi

        if [ $? -ne 0 ]; then
            log "ERROR" "docker exec failed, please check the container name"
        fi
        docker_command="docker exec -i $container_name"
    else
        log "INFO" "is_docker = false"
    fi

    command="mysqldump -h $host -P $port -u $username -p$password $database"
    local out_command
    if $is_docker; then
        out_command=" | gzip | docker exec -i $container_name sh -c 'cat > /tmp/$database.sql.gz' && docker cp $container_name:/tmp/$database.sql.gz $backup_root/$database.sql.gz && docker exec -i $container_name sh -c 'rm -rf /tmp/$database.sql.gz'"
    else
        out_command=" | gzip > $backup_root/$database.sql.gz"
    fi
    LOG "DEBUG" "docker_command: $docker_command"
    LOG "DEBUG" "out_command: $out_command"

    local full_command="$docker_command $command $out_command"
    log "INFO" "full_command: $full_command"

}

folder_task() {
    log "INFO" "folder_task"
    local config_snippet=$1
    local path

    path=$(jq -r '.path' <<<"$config_snippet")
    log "INFO" "path: $path"
    local command
    command="tar -zcvf $backup_root/$(basename $path)-$(date +%Y%m%d%H%M%S).tar.gz $path"
    log "INFO" "command: $command"
}

volume_task() {
    log "INFO" "volume_task"
    local config_snippet=$1
    local volume_name

    volume_name=$(jq -r '.volume_name' <<<"$config_snippet")
    log "INFO" "volume_name: $volume_name"
    local command
    command="docker run --rm -v $volume_name:/volume -v $backup_root:/backup alpine tar -zcvf /backup/$(basename $volume_name)-$(date +%Y%m%d%H%M%S).tar.gz /volume"
    log "INFO" "command: $command"
}

# main function
check_software
read_config
read_tasks
