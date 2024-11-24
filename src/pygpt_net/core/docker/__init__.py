#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# Created By  : Marcin Szczygliński                  #
# Updated Date: 2024.11.17 17:00:00                  #
# ================================================== #

import os
import docker
import io
import tarfile

from docker.errors import DockerException

class Docker:
    def __init__(self, plugin = None):
        self.plugin = plugin
        self.client = None
        self.container_name = "pygpt_container"
        self.image_name = "pygpt_image"
        self.initialized = False
        self.signals = None

    def get_dockerfile(self) -> str:
        """
        Get the Dockerfile

        :return: Dockerfile.
        """
        return self.plugin.get_option_value('ipython_dockerfile')

    def get_image_name(self) -> str:
        """
        Get the image name

        :return: Image name.
        """
        return self.plugin.get_option_value('ipython_image_name')

    def get_container_name(self) -> str:
        """
        Get the container name

        :return: Container name.
        """
        return self.plugin.get_option_value('ipython_container_name')

    def create_docker_context(self, dockerfile: str) -> io.BytesIO:
        """
        Create a Docker context with the specified Dockerfile content.

        :param dockerfile: Dockerfile content.
        :return: Docker context.
        """
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            dockerfile_info = tarfile.TarInfo('Dockerfile')
            dockerfile_data = dockerfile.encode('utf-8')
            dockerfile_info.size = len(dockerfile_data)
            tar.addfile(dockerfile_info, io.BytesIO(dockerfile_data))
        tar_stream.seek(0)
        return tar_stream

    def is_image(self):
        """Check if the Docker image exists."""
        client = self.get_docker_client()
        try:
            client.images.get(self.get_image_name())
            return True
        except docker.errors.ImageNotFound as e:
            print(e)
            return False

    def build_image(self):
        """Build the Docker image."""
        client = self.get_docker_client()
        context = self.create_docker_context(self.get_dockerfile())
        self.log("Please wait... Building the Docker image...")
        image, logs = client.images.build(
            fileobj=context,
            custom_context=True,
            rm=True,
            tag=self.get_image_name(),
        )
        for chunk in logs:
            if 'stream' in chunk:
                self.log(chunk['stream'].strip())

    def prepare_local_data_dir(self):
        """ Prepare the local data directory."""
        local_data_dir = self.get_local_data_dir()
        try:
            os.makedirs(local_data_dir)
        except FileExistsError:
            pass

    def get_docker_client(self) -> docker.DockerClient:
        """
        Get the Docker client.

        :return: Docker client.
        """
        return docker.from_env()

    def end(self, all: bool = False):
        """
        Stop all.

        :param all: Stop the container as well.
        """
        if all:
            self.stop_container(self.get_container_name())

    def stop_container(self, name: str):
        """
        Stop the Docker container.

        :param name: Container name.
        """
        client = self.get_docker_client()
        try:
            container = client.containers.get(name)
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            self.log(f"Container '{name}' not found.")

    def create_container(self, name: str):
        """
        Create the Docker container.

        :param name: Container name.
        """
        client = self.get_docker_client()
        local_data_dir = self.get_local_data_dir()
        image_name = self.get_image_name()

        try:
            container = client.containers.get(name)
            container.reload()
            if container.status == 'running':
                pass
            else:
                print(f"Container '{name}' is not running. Starting it.")
                container.remove()
                container = client.containers.create(
                    image=image_name,
                    name=name,
                    volumes={
                        local_data_dir: {
                            'bind': '/data',
                            'mode': 'rw',
                        }
                    },
                    tty=True,
                    stdin_open=True,
                    command='tail -f /dev/null'
                )
                container.start()
        except docker.errors.NotFound:
            print(f"Container '{name}' not found. Creating a new one.")
            container = client.containers.create(
                image=image_name,
                name=name,
                volumes={
                    local_data_dir: {
                        'bind': '/data',
                        'mode': 'rw',
                    }
                },
                tty=True,
                stdin_open=True,
                command='tail -f /dev/null'
            )
            container.start()
        except Exception as e:
            self.log(f"Error creating container: {e}")

    def execute(self, cmd: str) -> bytes or None:
        """
        Execute command in Docker container.

        :param cmd: Command to execute
        :return: Response
        """
        client = self.get_docker_client()
        name = self.get_container_name()

        # at first, check for image
        if not self.is_image():
            self.build_image()

        # run the container
        try:
            self.create_container(name)
            container = client.containers.get(name)
            result = container.exec_run(
                cmd,
                stdout=True,
                stderr=True,
            )
            tmp = result.output.decode("utf-8")
            response = tmp.encode("utf-8")
        except Exception as e:
            self.log(f"Error running container: {e}")
            response = str(e).encode("utf-8")
        return response

    def get_local_data_dir(self) -> str:
        """
        Get the local data directory.

        :return: Local data directory.
        """
        return self.plugin.window.core.config.get_user_dir("data")

    def is_docker_installed(self) -> bool:
        """
        Check if Docker is installed

        :return: True if installed
        """
        try:
            if self.client is None:
                client = docker.from_env()
                client.ping()
            return True
        except DockerException:
            return False

    def attach_signals(self, signals):
        """
        Attach signals

        :param signals: signals
        """
        self.signals = signals

    def log(self, msg):
        """
        Log the message.

        :param msg: Message to log.
        """
        print(msg)
