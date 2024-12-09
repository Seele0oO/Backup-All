import json

# 定义转换函数
def transform_json(source):
    # 转换 settings 部分
    new_settings = {
        "backup_root": source["settings"][0]["backup_root"],  # 从旧格式获取
        "backup_keep_days": int(source["settings"][0]["backup_keep_days"])  # 转换 backup_keep_days 为整数
    }

    # 转换 tasks 部分
    new_tasks = {
        "databases": {
            "mongodb": [],
            "mysql": []
        },
        "folders": [],
        "volumes": []
    }

    # 遍历旧的 tasks 并进行转换
    for task in source["tasks"]:
        if task["type"] == "mongodb":
            mongo_task = {
                "docker": {
                    "enabled": task["docker"]["is-docker"],  # 从旧格式转换
                    "container": task["docker"]["container_name"]
                },
                "host": task["host"],
                "port": int(task["port"]),
                "auth": {
                    "username": task["username"],
                    "password": task["password"]
                },
                "database": task["database"],
                "exclude": task["excludeCollection"]
            }
            new_tasks["databases"]["mongodb"].append(mongo_task)

        elif task["type"] == "mysql":
            mysql_task = {
                "docker": {
                    "enabled": task["docker"]["is-docker"],
                    "container": task["docker"]["container_name"]
                },
                "host": task["host"],
                "port": int(task["port"]),
                "auth": {
                    "username": task["username"],
                    "password": task["password"]
                },
                "database": task["database"]
            }
            new_tasks["databases"]["mysql"].append(mysql_task)

        elif task["type"] == "folder":
            folder_task = {
                "path": task["path"],
                "exclude": task["exclude"]
            }
            new_tasks["folders"].append(folder_task)

        elif task["type"] == "volume":
            volume_task = {
                "name": task["docker"]["volume_name"]
            }
            new_tasks["volumes"].append(volume_task)

    # 返回转换后的新 JSON 数据
    return {
        "settings": new_settings,
        "tasks": new_tasks
    }

# 读取文件并转换
if __name__ == '__main__':
    # 从文件读取旧的 JSON 数据
    with open('compant/old.json', 'r', encoding='utf-8') as f:
        source_json = f.read()

    # 解析 JSON 数据
    source = json.loads(source_json)

    # 进行转换
    result = transform_json(source)

    # 打印格式化后的结果
    print(json.dumps(result, indent=2, ensure_ascii=False))
