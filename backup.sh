#!/bin/bash

# 定义日志级别和日志文件
# log_LEVELS="DEBUG INFO WARNING ERROR CRITICAL"
log_FILE="./script.log"

Warning_hint() {
    echo -e "\033[31mIt's DANGEROUS to stop the script, please wait for the script to finish\033[0m"
    echo -e "\033[31m停止脚本是危险的，请等待脚本完成\033[0m"
    countdown() {
        local i=$1
        while [ $i -gt 0 ]; do
            echo -e "\033[32mPlease make a decision in the next $i seconds... Press Ctrl+C if you need to stop the operation.\033[0m"
            echo -e "\033[32m请在接下来的 $i 秒内做出决定...如果需要停止操作，请按 Ctrl+C。\033[0m"
            sleep 1
            echo -ne "\033[2A\033[0K"
            ((i--))
        done
        eval "clear"
        echo -e "\033[32mOperation confirmed.\033[0m"
        echo -e "\033[32m操作已确认。\033[0m"
    }
    countdown 5
}
# 日志函数
log() {
    local level=$1 msg=$2
    local timestamp=
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

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
# 检查 config_file 是否存在和格式错误
check_config_file() {
    config_file=$1
    if [ -z "${config_file}" ]; then
        log "CRITICAL" "No configuration file specified"
    elif [ ! -f "${config_file}" ]; then
        log "CRITICAL" "${config_file} does not exist"
    fi
    if jq -e .settings ${config_file} > /dev/null && jq -e .tasks ${config_file} > /dev/null; then
        log "INFO" "${config_file} is valid"
    else
        log "ERROR" "${config_file} is invalid"
    fi
    log "INFO" "config_file: ${config_file}"
}
# 读取全局配置文件
read_config() {
    config_file=$1
    check_config_file $config_file
    backup_root=$(jq -r '.settings[0].backup_root' ${config_file})
    backup_keep_days=$(jq -r '.settings[0].backup_keep_days' ${config_file})

    log "INFO" "backup_root: $backup_root"
    log "INFO" "backup_keep_days: ${backup_keep_days}"
}

read_tasks() {
    config_file=$1
    check_config_file $config_file
    log "INFO" "********read_tasks********"
    tasks=$(jq -c '.tasks[]' ${config_file})
    for task in $tasks; do
        read_a_task "$task"
    done
}

read_a_task() {
    local config_snippet=$1

    if jq -e . <<<"$config_snippet" >/dev/null; then
        task_type=$(jq -r '.type' <<<"$config_snippet")
        log "INFO" "There is a task config: $config_snippet"
        log "DEBUG" "task_type: $task_type"
        case "${task_type}" in
            mongodb)
                log "DEBUG" "task_type = mongodb"
                log "INFO" "host: $(jq -r '.host' <<<"$config_snippet")"
                log "INFO" "port: $(jq -r '.port' <<<"$config_snippet")"
                log "INFO" "username: $(jq -r '.username' <<<"$config_snippet")"
                log "INFO" "password: $(jq -r '.password' <<<"$config_snippet")"
                log "INFO" "database: $(jq -r '.database' <<<"$config_snippet")"
                log "INFO" "is-docker: $(jq -r '.docker."is-docker"' <<<"$config_snippet")"
                log "INFO" "container_name: $(jq -r '.docker.container_name' <<<"$config_snippet")"
            ;;
            mysql)
                log "DEBUG" "task_type = mysql"
                log "INFO" "host: $(jq -r '.host' <<<"$config_snippet")"
                log "INFO" "port: $(jq -r '.port' <<<"$config_snippet")"
                log "INFO" "username: $(jq -r '.username' <<<"$config_snippet")"
                log "INFO" "password: $(jq -r '.password' <<<"$config_snippet")"
                log "INFO" "database: $(jq -r '.database' <<<"$config_snippet")"
                log "INFO" "is-docker: $(jq -r '.docker."is-docker"' <<<"$config_snippet")"
                log "INFO" "container_name: $(jq -r '.docker.container_name' <<<"$config_snippet")"
            ;;
            folder)
                log "DEBUG" "task_type = folder"
                log "INFO" "path: $(
                    jq -r '.path' <<<"$config_snippet"
                )"
            ;;
            volume)
                log "DEBUG" "task_type = volume"
                log "INFO" "volume_name: $(
                    jq -r '.docker.volume_name' <<<"$config_snippet"
                )"
            ;;
            *)
                log "ERROR" "Invalid task type: $task_type"
            ;;
        esac
        
    else
        log "ERROR" "Invalid task config: $config_snippet"
    fi
}

run_tasks() {
    config_file=$1
    check_config_file $config_file
    log "INFO" "********run_tasks********"
    tasks=$(jq -c '.tasks[]' ${config_file})
    for task in $tasks; do
        run_a_task "$task"
    done
}

run_a_task() {
    local task=$1
    local task_type
    local backup_root
    backup_root=$(jq -r '.settings[0].backup_root' ${config_file})
    task_type=$(jq -r '.type' <<<"$task")
    log "DEBUG" "task_type: $task_type"
    case "${task_type}" in
        mongodb)
            log "DEBUG" "task_type = mongodb"
            mongodb_task $task
        ;;
        mysql)
            log "DEBUG" "task_type = mysql"
            mysql_task $task
        ;;
        folder)
            log "DEBUG" "task_type = folder"
            folder_task $task
        ;;
        volume)
            log "DEBUG" "task_type = volume"
            volume_task $task
        ;;
        *)
            log "ERROR" "Invalid task type: $task_type"
        ;;
    esac
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

regexp_container_name() {
    container_name=$1
    local result
    result=$(docker ps --format '{{.Names}}' | grep "^${container_name}" | tr ' ' '\n')
    # 计算结果数量
    local result_count
    result_count=$(echo -n "$result" | grep -c '^')
    if [ $result_count -gt 1 ]; then
        log "ERROR" "Find multiple containers named ${container_name}, please specify the container name"
    fi
    if [ -n "$result" ]; then
        log "DEBUG" "Find a container named ${container_name}"
        container_name=$result
        log "INFO" "container_name: ${container_name}"
    else
        log "ERROR" "Can't find a container named ${container_name}"
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
    if [ -z "$host" ] || [ -z "$port" ] || [ -z "${database}" ]; then
        log "ERROR" "host, port, database are required"
    fi
    # INFO username and password are optional
    if [ -z "$username" ] && [ -z "$password" ]; then
        log "WARNING" "username & password is empty,but it's optional"
    fi
    local command
    local docker_command
    local backup_filename

    if $is_docker; then
        log "INFO" "is_docker = true"
        container_name=$(jq -r '.docker.container_name' <<<"$config_snippet")
        log "DEBUG" "container_name: ${container_name}"
        regexp_container_name ${container_name}

        if [ $? -ne 0 ]; then
            log "ERROR" "docker exec failed, please check the container name"
        fi
        docker_command="docker exec -i ${container_name}"
        backup_filename="mongo_${database}_${container_name}_${host}_${port}"
    else
        log "DEBUG" "is_docker = false"
        backup_filename="mongo_${database}_${host}_${port}"
    fi


    # if without username & password
    if [ -z "$username" ]; then
        command=" mongodump --host $host --port $port --db ${database}"
        backup_filename="${backup_filename}"
    else
        command=" mongodump --host $host --port $port --username $username --password $password --db ${database}"
        backup_filename="${backup_filename}_${username}"
    fi

    local current_task_backup_folder
    current_task_backup_folder="${backup_root}/${backup_filename}"
    log "DEBUG" "current_task_backup_folder: $current_task_backup_folder"
    # create folder if not exit
    create_folder "$current_task_backup_folder"

    # export to specified folder
    local out_command=""
    if ${is_docker}; then
        out_command="--out /tmp/${database} && docker exec -i ${container_name} sh -c 'tar -zcvf /tmp/${database}.tar.gz /tmp/${database}'"
        out_command+=" && docker cp ${container_name}:/tmp/${database}.tar.gz $current_task_backup_folder/${database}-$(date +%Y%m%d%H%M%S).tar.gz"
        out_command+=" && docker exec -i ${container_name} sh -c 'rm -rf /tmp/${database}.tar.gz'"
    else
        out_command="--out $current_task_backup_folder/${database}"
        out_command+="&& tar -zcvf $current_task_backup_folder/${database}-$(date +%Y%m%d%H%M%S).tar.gz $current_task_backup_folder/${database}"
        out_command+="&& rm -rf $current_task_backup_folder/${database}"
    fi
    local full_command="$docker_command $command $out_command"
    log "DEBUG" "full_command: $full_command"
    eval $full_command >> ${log_FILE} 2>&1
    local exit_status=$?
    if [ ${exit_status} -eq 0 ]; then
        log "INFO" "Backup mongodb ${database} to $current_task_backup_folder success"
    else
        log "ERROR" "Backup mongodb ${database} to $current_task_backup_folder failed"
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
        log "DEBUG" "container_name: ${container_name}"
        regexp_container_name ${container_name}

        if [ $? -ne 0 ]; then
            log "ERROR" "docker exec failed, please check the container name"
        fi
        docker_command="docker exec -i ${container_name}"
    else
        log "DEBUG" "is_docker = false"
    fi

    command="mysqldump -h $host -P $port -u $username -p$password ${database}"
    local out_command
    # create folder if not exit
    # echo "Host value: $host"
    local current_task_backup_folder
    if ${is_docker}; then
        current_task_backup_folder="$backup_root/mysql_${database}_${container_name}_${host}_${port}"
    else
        current_task_backup_folder="$backup_root/mysql_${database}_${host}_${port}"
    fi
    log "DEBUG" "current_task_backup_folder: $current_task_backup_folder"
    create_folder "$current_task_backup_folder"
    
    if ${is_docker}; then
        out_command=" | gzip | docker exec -i ${container_name} sh -c 'cat > /tmp/${database}.sql.gz'"
        out_command+=" && docker cp ${container_name}:/tmp/${database}.sql.gz $current_task_backup_folder/${database}-$(date +%Y%m%d%H%M%S).sql.gz"
        out_command+=" && docker exec -i ${container_name} sh -c 'rm -rf /tmp/${database}.sql.gz'"
    else
        out_command=" | gzip > $current_task_backup_folder/${database}.sql.gz"
    fi
    log "DEBUG" "docker_command: $docker_command"
    log "DEBUG" "out_command: $out_command"

    local full_command="$docker_command $command $out_command"
    log "DEBUG" "full_command: $full_command"
    eval $full_command >> ${log_FILE} 2>&1
    if [ $? -eq 0 ]; then
        log "INFO" "Backup mysql ${database} to $current_task_backup_folder success"
    else
        log "ERROR" "Backup mysql ${database} to $current_task_backup_folder failed"
    fi
}

folder_task() {
    log "INFO" "********folder_task********"
    local config_snippet=$1
    local path
    local excludes
    local exclude_commands

    path=$(jq -r '.path' <<<"$config_snippet")
    excludes=$(jq -r '.exclude' <<<"$config_snippet")
    excludes=$(echo $excludes | tr -d '[],"')
    log "INFO" "excludes: $excludes"
    exclude_commands=""
    for exclude in $excludes; do
        exclude_commands+=" --exclude=$exclude"
    done
    log "INFO" "path: $path"
    local current_task_backup_folder
    current_task_backup_folder="$backup_root/folder_$(basename $path)"
    create_folder "$current_task_backup_folder"

    local command
    command="tar -zcvf $current_task_backup_folder/$(basename $path)-$(date +%Y%m%d%H%M%S).tar.gz $exclude_commands $path"
    log "DEBUG" "command: $command"
    eval $command >> ${log_FILE} 2>&1
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
    eval $full_command >> ${log_FILE} 2>&1
    if [ $? -eq 0 ]; then
        log "INFO" "Backup volume $volume_name to $current_task_backup_folder success"
    else
        log "ERROR" "Backup volume $volume_name to $current_task_backup_folder failed"
    fi
}

cleanup() {
    local backup_keep_days
    backup_keep_days=$(jq -r '.settings[0].backup_keep_days' ${config_file})
    log "DEBUG" "cleanup"
    local command
    local remove_empty_folders
    remove_empty_folders="find $backup_root -type d -empty -delete"
    command="find $backup_root \( -name '*.tar.gz' -o -name '*.tar' -o -name '*.gz' \) -type f -mtime +${backup_keep_days} -exec rm -rf {} \;"
    command+=" && $remove_empty_folders"
    log "DEBUG" "command: $command"
    eval $command >> ${log_FILE} 2>&1
    if [ $? -eq 0 ]; then
        log "INFO" "cleanup success"
    else
        log "ERROR" "cleanup failed"
    fi
}

display_help() {
    echo "Usage: $0 [-h] [-f] [-t]"
    echo "Options:"
    echo "  -h, --help  Display this help message."
    echo "  -f, --file  Specify the configuration file and run tasks."
    echo "  -t, --test  Test the configuration file."
    echo " Example: $0 -f config.json"
    echo " Example: $0 --test config.json"
}

read_args() {
    if [ $# -eq 0 ]; then
        display_help
    fi

    OPTIONS=$(getopt -o hf:t: --long help,file:,test: -- "$@")
    if [ $? -ne 0 ]; then
        echo "getopt error"
        exit 1
    fi
    
    eval set -- "$OPTIONS"
    
    while true; do
        case "$1" in
            -h|--help)
                display_help
                exit 0
            ;;
            -f|--file)
                shift
                Warning_hint
                run_tasks "$1"
                cleanup "$1"
                shift
                break
            ;;
            -t|--test)
                shift
                read_config "$1"
                read_tasks "$1"
                shift
                break
            ;;
            --)
                shift
                break
            ;;
            *)
                echo "Invalid option: -$1" >&2
                exit 1
            ;;
        esac
    done
}




check_software
read_args "$@"