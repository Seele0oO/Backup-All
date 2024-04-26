#!/bin/bash

# 备份目录配置
export BACKUP_FOLDER="/localbackup"

# 数据库配置
export MYSQL_IS_CONTAINER=false
export MYSQL_CONTAINER_NAME="mysql"
export MYSQL_USERNAME="username"
export MYSQL_PASSWORD="password"
export MYSQL_DATABASES=("rctechx" "imprint")

export MONGODB_IS_CONTAINER=true
export MONGODB_CONTAINER_NAME="mongodb_container"
export MONGODB_USERNAME="username"
export MONGODB_PASSWORD="password"
export MONGODB_DATABASE="database"

export RABBITMQ_IS_CONTAINER=true
export RABBITMQ_CONTAINER_NAME="rabbit_container"
export RABBITMQ_HOST="localhost"
export RABBITMQ_PORT="15672"
export RABBITMQ_CONTAINER_NAME="rabbitmq_container_name"

# Docker 卷配置
# export VOLUME_NAMES=("es_data" "es_data_backup")

# 目录备份配置
export DIRECTORY_PATHS=("/data/deploy-scripts","/data/docker_data")

# 备份保留数量
export BNUM=4

