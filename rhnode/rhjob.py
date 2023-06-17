from pathlib import Path
import requests
from pydantic import BaseModel
import time
import os
from .common import *
import json
from requests.exceptions import HTTPError



class RHJob:
    def __init__(
        self,
        node_name,
        inputs,
        output_directory=None,
        node_address=None,
        manager_address=None,
        resources_included=False,
        included_cuda_device=None,
        check_cache=True,
        save_to_cache=True,
        priority=2,
        save_non_files=False,
        _cli_mode=False,
    ):
        self._cli_mode = _cli_mode
        if self._cli_mode:
            assert isinstance(
                inputs, list
            ), "inputs must be a list of arguments in _cli_mode"
        else:
            assert isinstance(
                inputs, dict
            ), "inputs must be a dict of arguments if not in _cli_mode"

        self.save_non_files = save_non_files
        self.node_identifier = node_name

        self.input_output_data = inputs.copy()

        self.job = JobMetaData(
            device=included_cuda_device,
            check_cache=check_cache,
            save_to_cache=save_to_cache,
            priority=priority,
            directory=None,
            resources_included=resources_included,
        )
        if node_address is not None:
            self.host, self.port = node_address.split(":")
        else:
            self.host = None
            self.port = None

        self.ID = None
        self.strict_output_dir = False
        if output_directory is None:
            output_directory = "."
        else:
            self.strict_output_dir = True

        self.output_directory = output_directory
        if (self.port is None) ^ (self.host is None):
            raise Exception("Specify both port and host or neither")

        if self.host is None:
            if manager_address is None:
                options = [
                    ("manager", "8000"),
                    ("localhost", "9050"),
                    ("titan6", "9050"),
                ]
                self.manager_host, self.manager_port = self.select_manager_endpoint(
                    options
                )
            else:
                self.manager_host, self.manager_port = manager_address.split(":")

    @staticmethod
    def from_parent_job(node_name, inputs, parent_job, use_same_resources=False):
        included_device = (
            parent_job.device
            if use_same_resources or parent_job.resources_included
            else None
        )
        return RHJob(
            node_name=node_name,
            inputs=inputs,
            check_cache=parent_job.check_cache,
            save_to_cache=parent_job.save_to_cache,
            priority=parent_job.priority,
            resources_included=parent_job.resources_included or use_same_resources,
            included_cuda_device=included_device,
            output_directory=_create_output_directory(parent_job.directory, node_name),
        )

    def _maybe_make_output_directory(self, output_directory):
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

    def is_manager_endpoint_responsive(self, host, port):
        try:
            url = f"http://{host}:{port}/manager/ping"
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except (requests.exceptions.RequestException, ValueError):
            pass
        return False

    def select_manager_endpoint(self, options):
        for host, port in options:
            print("Looking for manager at", ":".join([host, port]), "...")
            if self.is_manager_endpoint_responsive(host, port):
                print("Manager found at", ":".join([host, port]), "...")
                return host, port
        raise Exception("No responsive manager endpoint found in the provided options.")

    def _parse_endpoint(self, adress):
        host, _ = adress.split(":")

        if host == "localhost" and self.manager_host == "manager":
            return self.node_identifier + ":8000"
        elif host == "localhost":
            return self.manager_host + ":" + self.manager_port
        else:
            return adress

    def _get_addr_for_job(self, node):
        url = f"http://{self.manager_host}:{self.manager_port}/manager/dispatcher/get_host/{node}"
        response = requests.get(url)
        response.raise_for_status()
        addr = response.json()
        addr = self._parse_endpoint(addr)
        return addr.split(":")

    def stop(self):
        assert self.ID is not None, "Not started"
        print("Stopping", self.ID, "...")
        url = (
            f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/stop"
        )
        response = requests.post(url)
        response.raise_for_status()

        response = None
        sucess = False
        for i in range(10):
            print("Trying to stop job...")
            url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/status"

            response = requests.get(url)
            response.raise_for_status()
            status = response.json()

            if JobStatus(status) == JobStatus.Cancelled:
                sucess = True
                break

            time.sleep(3)

        if not sucess:
            raise Exception("Could not stop job")

        print("Stopped", self.ID)

    def _split_input_output_data(self, input_output_data):
        input_data = {}
        output_data = {}

        url = f"http://{self.host}:{self.port}/{self.node_identifier}/keys"
        response = requests.get(url)
        response.raise_for_status()
        keys = response.json()
        input_keys = keys["input_keys"]
        output_keys = keys["output_keys"]

        for key, value in input_output_data.items():
            if key in input_keys:
                input_data[key] = value
            elif key in output_keys:
                output_data[key] = value
            else:
                raise Exception(f"Key '{key}' not found in input or output keys")
        return input_data, output_data

    def print_cli_help(self):
        if not self.host:
            self.host, self.port = self._get_addr_for_job(self.node_identifier)

        self._print_help_cli()

    def start(self):
        assert self.ID is None, "Already started"

        if not self.host:
            self.host, self.port = self._get_addr_for_job(self.node_identifier)

        if self._cli_mode:
            self.input_output_data = self._parse_cli(self.input_output_data)

        self.input_data, self.output_data = self._split_input_output_data(
            self.input_output_data
        )

        input_data = replace_paths_with_strings(self.input_data)

        url = f"http://{self.host}:{self.port}/{self.node_identifier}/filename_keys"
        print(url)
        response = requests.get(url)
        response.raise_for_status()
        file_keys = response.json()
        input_data_files = {}
        input_data_not_files = {}
        for key, value in input_data.items():
            if key in file_keys:
                input_data_files[key] = value
            else:
                input_data_not_files[key] = value

        ## Setup the thing
        print(input_data_not_files)
        url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs"
        print(f"Creating new job on {self.host}:{self.port}")
        response = requests.post(url, json=input_data_not_files)
        response.raise_for_status()
        self.ID = response.json()

        ## Upload the files
        data = {}
        for key, value in input_data_files.items():
            url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/upload"
            with open(value, "rb") as f:
                print(
                    f"Uploading file to {self.host}:{self.port}:",
                    key,
                    ":",
                    value,
                )
                files = {"file": f}
                data["key"] = key
                response = requests.post(url, files=files, data=data)
                response.raise_for_status()

        ## RUN The thing

        # data = {"test": "hejsa"}
        print(data)
        print(f"Starting job on {self.host}:{self.port} with ID:", self.ID)
        url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/start"
        response = requests.post(url, json=self.job.dict())
        response.raise_for_status()

        print(self.node_identifier, "job submitted with ID:", self.ID, "to", self.host)

    def _get_status(self):
        url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/status"

        response = requests.get(url)
        response.raise_for_status()
        response_json = response.json()
        status = response_json
        return status

    def wait_for_finish(self):
        assert self.ID is not None, "Not started"
        if self.strict_output_dir:
            output_path = self.output_directory
        else:
            output_path = _create_output_directory_name(self.output_directory, self.node_identifier)

        output = None
        while output is None:
            status = self._get_status()
            if JobStatus(status) == JobStatus.Finished:
                url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/data"
                response = requests.get(url)
                response.raise_for_status()
                output = response.json()
            elif JobStatus(status) == JobStatus.Error:
                url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/error"
                response = requests.get(url)
                response.raise_for_status()
                response_json = response.json()
                raise JobFailedError(
                    "The job exited with an error: "
                    + response_json["error"]
                    + response_json["traceback"]
                )
            elif JobStatus(status) == JobStatus.Cancelled:
                raise JobCancelledError("The job was cancelled")
            elif JobStatus(status) == JobStatus.Queued:
                time.sleep(10)
            elif JobStatus(status) == JobStatus.Running:
                time.sleep(4)

        for key, value in output.items():
            if isinstance(value, str) and "/download/" in value:
                print("Downloading", key, "...")
                url = f"http://{self.host}:{self.port}/{self.node_identifier}/jobs/{self.ID}/download/{key}"

                response = requests.get(url)
                response.raise_for_status()

                if not key in self.output_data.keys():
                    fname = (
                        response.headers["Content-Disposition"]
                        .split("=")[1]
                        .replace('"', "")
                    )
                    self._maybe_make_output_directory(output_path)
                    fname = Path(os.path.join(output_path, fname)).absolute()
                else:
                    fname = Path(self.output_data[key]).absolute()

                with open(fname, "wb") as f:
                    f.write(response.content)
                output[key] = fname

            elif key in self.output_data.keys():
                fname = Path(self.output_data[key]).absolute()

                with open(fname, "w") as f:
                    f.write(str(value))

            elif self.save_non_files:
                self._maybe_make_output_directory(output_path)
                fname = Path(os.path.join(output_path, key)).absolute()

                with open(fname, "w") as f:
                    f.write(str(value))

        return output

    def _parse_cli(self, input_output_data):
        try:
            url = f"http://{self.host}:{self.port}/{self.node_identifier}/cli/parse"
            response = requests.post(url, json=input_output_data)
            response.raise_for_status()

        except HTTPError as err:
            if err.response.status_code == 400:
                raise ValueError(
                    f"Invalid CLI arguments for {self.node_identifier}:\n{err.response.json()['detail']}"
                )
            else:
                raise

        return response.json()

    def _print_help_cli(self):
        url = f"http://{self.host}:{self.port}/{self.node_identifier}/cli/help"
        response = requests.get(url)
        response.raise_for_status()
        print(response.json())


def replace_paths_with_strings(inp):
    if isinstance(inp, BaseModel):
        inp = inp.dict()
    for key, val in inp.items():
        if isinstance(val, Path):
            inp[key] = str(val)
        else:
            inp[key] = val
    return inp


def _create_output_directory_name(base_directory, node_name):
    directory = os.path.join(base_directory, node_name)
    i = 1
    while True:
        if not os.path.exists(directory):
            break
        directory = os.path.join(base_directory, node_name + "_" + str(i))
        i += 1
    return directory


def _create_output_directory(base_directory, node_name):
    directory = _create_output_directory_name(base_directory, node_name)
    os.makedirs(directory)
    return directory
