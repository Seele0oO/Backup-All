#!/bin/bash

# 定义日志级别和日志文件
log_LEVELS="DEBUG INFO WARNING ERROR CRITICAL"
log_FILE="./my_script.log"

Warning_hint() {
    echo -e "\033[31mIt's DANGEROUS to stop the script, please wait for the script to finish\033[0m"
    echo -e "\033[31m停止脚本是危险的，请等待脚本完成\033[0m"
    echo -e "\033[32mOperation confirmed. Waiting for 5 seconds...\033[0m"
    echo -e "\033[32m操作已确认。等待5秒...\033[0m"
    sleep 5
}
# 日志函数
log() {
    local level=$1 msg=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        DEBUG)
            echo "$timestamp [$level] $msg" >> "$log_FILE"
        ;;
        INFO)
            echo -e "\033[32m$timestamp [$level] $msg\033[0m"
            echo "$timestamp [$level] $msg" >> "$log_FILE"
        ;;
        WARNING)
            echo -e "\033[43;37m$timestamp [$level] $msg\033[0m"
            echo "$timestamp [$level] $msg" >> "$log_FILE"
        ;;
        ERROR)
            echo -e "\033[31m$timestamp [$level] $msg\033[0m"
            echo "$timestamp [$level] $msg" >> "$log_FILE"
            exit 1
        ;;
        CRITICAL)
            echo -e "\033[31m$timestamp [$level] $msg\033[0m"
            echo "$timestamp [$level] $msg" >> "$log_FILE"
            exit 1
        ;;
        *)
            echo -e "\033[31mInvalid log level: $level\033[0m"
            exit 1
    esac


    # if [[ "$level" == "ERROR" || "$level" == "CRITICAL" ]]; then
    #     echo "$timestamp [$level] $msg"
    #     echo "$timestamp [$level] $msg" >> "$log_FILE"
    #     exit 1
    # else
    #     echo "$timestamp [$level] $msg"
    #     echo "$timestamp [$level] $msg" >> "$log_FILE"
    # fi
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

    log "INFO" "backup_root: $backup_root"
    log "INFO" "backup_keep_days: ${backup_keep_days}"
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
        log "DEBUG" "task_type: $task_type"
        case "${task_type}" in
            mongodb)
                log "DEBUG" "task_type = mongodb"
                mongodb_task $config_snippet
            ;;
            mysql)
                log "DEBUG" "task_type = mysql"
                mysql_task $config_snippet
            ;;
            folder)
                log "DEBUG" "task_type = folder"
                folder_task $config_snippet
            ;;
            volume)
                log "DEBUG" "task_type = volume"
                volume_task $config_snippet
            ;;
            *)
                log "ERROR" "Invalid task type: $task_type"
            ;;
        esac
        
    else
        log "ERROR" "Invalid task config: $config_snippet"
    fi
}

create_folder() {
    local folder=$1
    if [ ! -d "$folder" ]; then
        mkdir -p "$folder"
        log "INFO" "Create folder: $folder"
    else
        log "INFO" "Folder already exists: $folder"
    fi
}

mongodb_task() {
    log "INFO" "********mongodb_task********"
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
    if [ -z "$username" ] && [ -z "$password" ]; then
        log "WARNING" "username & password is empty,but it's optional"
    fi
    local command
    local docker_command

    if $is_docker; then
        log "INFO" "is_docker = true"
        container_name=$(jq -r '.docker.container_name' <<<"$config_snippet")
        log "DEBUG" "container_name: $container_name"
        result=$(docker ps -q --filter "name=^/$container_name")
        if [ -n "$result" ]; then
            log "DEBUG" "Find a container named $container_name"
        else
            log "ERROR" "Can't find a container named $container_name"
        fi

        if [ $? -ne 0 ]; then
            log "ERROR" "docker exec failed, please check the container name"
        fi
        docker_command="docker exec -i $container_name"
    else
        log "DEBUG" "is_docker = false"
    fi

    # if without username & password
    if [ -z "$username" ]; then
        command=" mongodump --host $host --port $port --db $database"
    else
        command=" mongodump --host $host --port $port --username $username --password $password --db $database"
    fi

    # create folder if not exit
    local current_task_backup_folder="$backup_root/mongo_$database_${host}_$port"
    create_folder "$current_task_backup_folder"

    # export to specified folder
    local out_command=""
    if $is_docker; then
        out_command="--out /tmp/$database | gzip | docker exec -i $container_name sh -c 'cat > /tmp/$database.tar.gz'"
        out_command+=" && docker cp $container_name:/tmp/$database.tar.gz $current_task_backup_folder/$database-$(date +%Y%m%d%H%M%S).tar.gz"
        out_command+=" && docker exec -i $container_name sh -c 'rm -rf /tmp/$database.tar.gz'"
        # out_command="--out /tmp/$database && docker cp $container_name:/tmp/$database $backup_root/$database && docker exec -i $container_name sh -c 'rm -rf /tmp/$database'"
    else
        out_command="--out $current_task_backup_folder/$database"
    fi

    local full_command="$docker_command $command $out_command"

    log "DEBUG" "full_command: $full_command"
    eval $full_command
    if [ $? -eq 0 ]; then
        log "INFO" "Backup mongodb $database to $current_task_backup_folder success"
    else
        log "ERROR" "Backup mongodb $database to $current_task_backup_folder failed"
    fi
}

mysql_task() {
    log "INFO" "********mysql_task********"
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
        log "DEBUG" "container_name: $container_name"
        result=$(docker ps -q --filter "name=^/$container_name")
        if [ -n "$result" ]; then
            log "DEBUG" "Find a container named $container_name"
        else
            log "ERROR" "Can't find a container named $container_name"
        fi

        if [ $? -ne 0 ]; then
            log "ERROR" "docker exec failed, please check the container name"
        fi
        docker_command="docker exec -i $container_name"
    else
        log "DEBUG" "is_docker = false"
    fi

    command="mysqldump -h $host -P $port -u $username -p$password $database"
    local out_command
    # create folder if not exit
    # echo "Host value: $host"
    local current_task_backup_folder="$backup_root/mysql_$database_${host}_$port"
    create_folder "$current_task_backup_folder"
    
    if $is_docker; then
        out_command=" | gzip | docker exec -i $container_name sh -c 'cat > /tmp/$database.sql.gz'"
        out_command+=" && docker cp $container_name:/tmp/$database.sql.gz $current_task_backup_folder/$database-$(date +%Y%m%d%H%M%S).sql.gz"
        out_command+=" && docker exec -i $container_name sh -c 'rm -rf /tmp/$database.sql.gz'"
    else
        out_command=" | gzip > $current_task_backup_folder/$database.sql.gz"
    fi
    log "DEBUG" "docker_command: $docker_command"
    log "DEBUG" "out_command: $out_command"

    local full_command="$docker_command $command $out_command"
    log "DEBUG" "full_command: $full_command"
    eval $full_command
    if [ $? -eq 0 ]; then
        log "INFO" "Backup mysql $database to $current_task_backup_folder success"
    else
        log "ERROR" "Backup mysql $database to $current_task_backup_folder failed"
    fi
}

folder_task() {
    log "INFO" "********folder_task********"
    local config_snippet=$1
    local path

    path=$(jq -r '.path' <<<"$config_snippet")
    log "DEBUG" "path: $path"
    local current_task_backup_folder
    current_task_backup_folder="$backup_root/folder_$(basename $path)"
    create_folder "$current_task_backup_folder"

    local command
    command="tar -zcvf $current_task_backup_folder/$(basename $path)-$(date +%Y%m%d%H%M%S).tar.gz $path"
    log "DEBUG" "command: $command"
    eval $command
    if [ $? -eq 0 ]; then
        log "INFO" "Backup folder $path to $current_task_backup_folder success"
    else
        log "ERROR" "Backup folder $path to $current_task_backup_folder failed"
    fi
}

volume_task() {
    log "INFO" "********volume_task********"
    local config_snippet=$1
    local volume_name

    volume_name=$(jq -r '.docker.volume_name' <<<"$config_snippet")
    log "DEBUG" "volume_name: $volume_name"

    # create folder if not exit
    local current_task_backup_folder="$backup_root/volume_$volume_name"
    create_folder "$current_task_backup_folder"

    # create tar && check tarfile is vaild &&remove origin folder
    local tar_filename
    tar_filename="$current_task_backup_folder/$volume_name-$(date +%Y%m%d%H%M%S).tar.gz"

    local command
    command="docker run --rm -v $volume_name:/volume -v $current_task_backup_folder:/backup alpine"
    command+=" tar -cvf /backup/$volume_name-$(date +%Y%m%d%H%M%S).tar /volume"
    log "DEBUG" "command: $command"

    local full_command="$command"
    log "DEBUG" "full_command: $full_command"
    log "DEBUG" "tar_filename: $tar_filename"
    eval $full_command
    if [ $? -eq 0 ]; then
        log "INFO" "Backup volume $volume_name to $current_task_backup_folder success"
    else
        log "ERROR" "Backup volume $volume_name to $current_task_backup_folder failed"
    fi
}

cleanup() {
    log "DEBUG" "cleanup"
    local command
    command="find $backup_root \( -name '*.tar.gz' -o -name '*.tar' -o -name '*.gz' \) -type f -mtime +${backup_keep_days} -exec rm -rf {} \;"
    log "DEBUG" "command: $command"
    eval $command
    if [ $? -eq 0 ]; then
        log "DEBUG" "cleanup success"
    else
        log "ERROR" "cleanup failed"
    fi
}

# main function
Warning_hint
check_software
read_config
read_tasks
cleanup