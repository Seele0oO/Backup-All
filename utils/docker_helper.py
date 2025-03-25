import docker
import re
from typing import Optional

class DockerHelper:
    def __init__(self):
        self.client = docker.from_env()

    def get_container(self, name_pattern: str) -> docker.models.containers.Container:
        """根据名称模式获取容器（兼容旧版 Docker，不依赖 SDK filters）"""
        try:
            all_containers = self.client.containers.list(all=False)  # 获取全部容器（不包括停止的）
        except Exception as e:
            raise RuntimeError(f"无法获取容器列表：{e}")

        # 使用正则表达式手动匹配容器名
        regex = re.compile(name_pattern)
        matched = [c for c in all_containers if regex.search(c.name)]

        if not matched:
            raise ValueError(f"No container found matching pattern: {name_pattern}")
        if len(matched) > 1:
            raise ValueError(f"Multiple containers found matching pattern: {name_pattern}")
        return matched[0]

    def exec_in_container(self, container, command: str) -> tuple:
        """在容器中执行命令"""
        result = container.exec_run(command, demux=True)
        return result
