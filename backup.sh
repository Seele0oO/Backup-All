#!/bin/bash
# 检测是否安装必要软件，如 jq,tar ,如果没有安装，提示安装并退出脚本
check_software() {
    if ! command -v jq &> /dev/null; then
        echo "jq is not installed, please install jq first"
        exit 1
    fi
    if ! command -v tar &> /dev/null; then
        echo "tar is not installed, please install tar first"
        exit 1
    fi
}
# 读取全局配置文件
read_config() {
    if [ ! -f "config.json" ]; then
        echo "config.json does not exist"
        exit 1
    fi
    backup_root=$(jq -r '.settings[0].backup_root' config.json)

    backup_keep_days=$(jq -r '.settings[0].backup_keep_days' config.json)

    docker_root=$(jq -r '.settings[0].docker_root' config.json)

    printf "backup_root: %s\nbackup_keep_days: %s\ndocker_root: %s\n" $backup_root $backup_keep_days $docker_root
}

read_a_config() {
    local config_snippet=$1

    if jq -e . <<<"$config_snippet" >/dev/null; then
        task_type=$(jq -r '.type' <<<"$config_snippet")
        printf "task_type: %s\n" "$task_type"
        case "${task_type}" in
            mongodb)
                echo "task_type = mongodb"
            ;;
            mysql)
                echo "task_type = mysql"
            ;;
            folder)
                echo "task_type = folder"
            ;;
            volume)
                echo "task_type = volume"
            ;;
            *)
                echo "ERROR: Unknown task_type: $task_type" >&2
            ;;
        esac
        
    else
        echo "Invalid JSON" >&2
        exit 1
    fi
}

read_tasks() {
    if [ ! -f "config.json" ]; then
        echo "config.json does not exist"
        exit 1
    fi
    tasks=$(jq -c '.tasks[]' config.json)
    for task in $tasks; do
        read_a_config "$task"
    done
}

# main function
check_software
read_config
read_tasks
