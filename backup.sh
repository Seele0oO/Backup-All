#!/bin/bash

# 加载配置
source backup_config.sh

echo 'Starting backup...'
overall_start_time=$(date +%s)

# 创建日志文件
log_file="$BACKUP_FOLDER/backup_$(date '+%Y-%m-%d').log"
touch "$log_file"

# 检查是否设置了必要的配置变量
if [ -z "$BACKUP_FOLDER" ] || [ -z "$BNUM" ]; then
    echo "ERROR: Backup configuration is incomplete. Please check your configuration file."
    exit 1
fi

# 日志记录函数
log_backup_result() {
    local status=$1
    local entity=$2
    local duration=$3
    local message=$4
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_message="$timestamp - $entity backup $status, took $duration seconds $message"
    echo "$log_message" >> "$log_file"
    echo "$log_message"
}

# 调用备份函数
# 备份Dictionary
if [ ${#DIRECTORY_PATHS[@]} -gt 0 ]; then
    for directory_path in "${DIRECTORY_PATHS[@]}"; do
        backup_directory "$directory_path"
    done
fi

# 备份函数
function backup_data() {
    local entity_type=$1
    local entity_name=$2
    local extra_args=$3
    local backup_extension=$4
    local command_to_run=$5
    
    local date_suffix=$(date "+%Y-%m-%d-%H%M%S")
    local backup_file_name="${entity_name}_${date_suffix}.${backup_extension}"
    local full_backup_path="$backup_folder/$backup_file_name"
    local start_time=$(date +%s)
    
    echo "Running backup for $entity_type $entity_name..."
    eval "$command_to_run" > "$full_backup_path"
    local command_status=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local message=""
    
    if [ $command_status -eq 0 ] && [ -f "$full_backup_path" ]; then
        log_backup_result "success" "$entity_name" "$duration" "$message"
    else
        message=", command exited with status $command_status"
        log_backup_result "failed" "$entity_name" "$duration" "$message"
    fi
    
    # 清理旧的备份文件，只保留最新的Bnum个
    local backups=($(ls -t $backup_folder/${entity_name}_*.$backup_extension))
    if [ ${#backups[@]} -gt $Bnum ]; then
        for ((i=$Bnum; i<${#backups[@]}; i++)); do
            echo "Removing old backup: ${backups[$i]}"
            rm -f "${backups[$i]}"
        done
    fi
}

function check_backup_is_vaild(){
    # 检测文件是否存在
    # 检测文件大小是否大于0
    # 检测压缩包能否被正确测试
    # 对于sql文件,或许可以做个东西去测试语法问题
}

# 备份特定卷的函数调用
function backup_volume() {
    local volume_name=$1
    local container_path="/${volume_name}_vol"
    local command_to_run="docker run --rm -v ${volume_name}:${container_path} -v $backup_folder:/backup alpine sh -c 'cd ${container_path} && tar cvfz /backup/${volume_name}_data_$(date +%Y-%m-%d-%H%M%S).tar.gz ./*'"
    backup_data "Volume" "$volume_name" "" "tar.gz" "$command_to_run"
}

# 备份Volume
if [ ${#VOLUME_NAMES[@]} -gt 0 ]; then
    for volume_name in "${VOLUME_NAMES[@]}"; do
        backup_volume "$volume_name"
    done
fi

# 备份数据库
if [ -n "$MYSQL_IS_CONTAINER" ] && [ -n "$MYSQL_USERNAME" ] && [ -n "$MYSQL_PASSWORD" ] && [ -n "$MYSQL_DATABASES" ]; then
    for MYSQL_DATABASE in "${MYSQL_DATABASES[@]}"; do
        if [ "$MYSQL_IS_CONTAINER" = "true" ]; then
            local CONTAINER_ID=$(docker ps --filter "label=com.docker.swarm.service.name='$MYSQL_CONTAINER_NAME'" --format "{{.ID}}")
            echo $CONTAINER_ID
            docker exec $CONTAINER_ID mysqldump -u $MYSQL_USERNAME -p$MYSQL_PASSWORD $MYSQL_DATABASE > $BACKUP_FOLDER/mysql_database_$(date '+%Y-%m-%d-%H%M%S').sql
        else
            # MySQL数据库运行在宿主机上
            backup_data "MySQL database" "database" "sql" "mysqldump -u $MYSQL_USERNAME -p$MYSQL_PASSWORD $MYSQL_DATABASE > $BACKUP_FOLDER/mysql_database_$(date '+%Y-%m-%d-%H%M%S').sql"
        fi
        echo "Database $MYSQL_DATABASE Backup May done."
    done
fi

if [ -n "$MONGODB_IS_CONTAINER" ] && [ -n "$MONGODB_USERNAME" ] && [ -n "$MONGODB_PASSWORD" ] && [ -n "$MONGODB_DATABASE" ]; then
    if [ "$MONGODB_IS_CONTAINER" = "true" ]; then
        local CONTAINER_ID=$(docker ps --filter "label=com.docker.swarm.service.name='$MONGODB_CONTAINER_NAME'" --format "{{.ID}}")
        echo $CONTAINER_ID
        # 在容器内执行 mongodump 创建备份
        docker exec $CONTAINER_ID mongodump --username $MONGODB_USERNAME --password $MONGODB_PASSWORD --db $MONGODB_DATABASE --archive="/tmp/$BACKUP_FILENAME" --gzip
        docker cp $CONTAINER_ID:/tmp/$BACKUP_FILENAME $BACKUP_FOLDER/$BACKUP_FILENAME
        docker exec $CONTAINER_ID rm -f /tmp/$BACKUP_FILENAME
    else
        backup_data "MongoDB database" "database" "gz" "mongodump --username $MONGODB_USERNAME --password $MONGODB_PASSWORD --db $MONGODB_DATABASE --archive=$BACKUP_FOLDER/mongodb_database_$(date '+%Y-%m-%d-%H%M%S').gz --gzip"
    fi
fi

if [ -n "$RABBITMQ_IS_CONTAINER"] && [ -n "$RABBITMQ_HOST" ] && [ -n "$RABBITMQ_PORT" ] && [ -n "$RABBITMQ_CONTAINER_NAME" ]; then
    local CONTAINER_ID=$(docker ps --filter "label=com.docker.swarm.service.name='$RABBITMQ_CONTAINER_NAME'" --format "{{.ID}}")
    echo $CONTAINER_ID
    backup_data "RabbitMQ config" "$CONTAINER_ID" "json" "rabbitmqadmin -H $RABBITMQ_HOST -P $RABBITMQ_PORT export $BACKUP_FOLDER/rabbitmq_config_$(date '+%Y-%m-%d-%H%M%S').json"
fi

overall_end_time=$(date +%s)
overall_duration=$((overall_end_time - overall_start_time))
echo "Backup process completed in $overall_duration seconds. Check $log_file for details."
