import docker
from typing import Optional

class DockerHelper:
    def __init__(self):
        self.client = docker.from_env()

    def get_container(self, name_pattern: str) -> docker.models.containers.Container:
        """根据名称模式获取容器"""
        containers = self.client.containers.list(filters={"name": f"^{name_pattern}"})
        if not containers:
            raise ValueError(f"No container found matching pattern: {name_pattern}")
        if len(containers) > 1:
            raise ValueError(f"Multiple containers found matching pattern: {name_pattern}")
        return containers[0]

    def exec_in_container(self, container, command: str) -> tuple:
        """在容器中执行命令"""
        result = container.exec_run(command, demux=True)
        return result
