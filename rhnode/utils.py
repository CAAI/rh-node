from pathlib import Path
import requests
from enum import Enum
import uuid
from pydantic import BaseModel, DirectoryPath
import time
import os 
from typing import Union

class Job(BaseModel):
    device: Union[None, int]
    check_cache: bool = True
    save_to_cache: bool = True
    priority: int = 2
    directory: Union[None, DirectoryPath] = None
    resources_included: bool = False

class QueueStatus(Enum):
    Preparing= -1 #Files are being uploaded
    Initializing = 0 #The job is being initialized
    Queued = 1 #THe job is queued
    Running = 2 #The job is running
    Finished = 3 #The job is finished
    Error = 4 #The job has encountered an error
    Cancelling = 5 #The job is being cancelled
    Cancelled = 6 #The job has been cancelled

class Node(BaseModel):
    name: str
    last_heard_from: float
    gpu_gb_required: float
    cores_required: int
    memory_required: int

class JobRequest(BaseModel):
    job_id: str
    priority: int
    required_gpu_mem: int
    required_cores: int
    required_memory: int

    
def new_job(check_cache = True, save_to_cache = True,priority = 2):
    job = Job(device = None,
        check_cache = check_cache,
        save_to_cache = save_to_cache,
        directory=None,
        priority = priority)
    return job

class NodeRunner:

    def __init__(self, identifier, inputs, job, port = None, host=None,output_directory=None,manager_adress=None,resources_included=False):
        self.identifier = identifier
        self.input_data = inputs.copy()
        self.job = job.copy()
        self.port = port
        self.ID = None
        self.host = host
        self.strict_output_dir = False
        if output_directory is None:
            if job.directory is not None:
                output_directory = job.directory
            else:
                output_directory = "."
        else:
            assert job.directory is None, "Cannot specify outputdirectory when job.directory is set"
            self.strict_output_dir = True

        self.job.directory = None
        if not resources_included:
            self.job.device = None
        self.job.resources_included = resources_included

        self.output_directory = output_directory
        if (port is None ) ^ (host is None):
            raise Exception("Specify both port and host or neither")
        
        if host is None:
            if manager_adress is None:
                options = [
                    ("manager", "8000"),
                    ("localhost", "9050"),
                ]
                self.manager_host, self.manager_port = self.select_manager_endpoint(options)
            else:
                self.manager_host, self.manager_port = manager_adress.split(":")


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
            print("Looking for manager at", ":".join([host,port]), "...")
            if self.is_manager_endpoint_responsive(host, port):
                print("Manager found at", ":".join([host,port]), "...")
                return host, port
        raise Exception("No responsive manager endpoint found in the provided options.")

    def _parse_endpoint(self, adress):
        host, _ = adress.split(":")

        if host == "localhost" and self.manager_host == "manager":
            return self.identifier+ ":8000" 
        elif host == "localhost":
            return self.manager_host+":"+self.manager_port
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
        print("Stopping",self.ID,"...")
        url = f"http://{self.host}:{self.port}/{self.identifier}/remove/{self.ID}"
        response = requests.post(url)
        response.raise_for_status()

        response = None
        sucess = False
        for i in range(10):
            print("Trying to stop job...")
            url = f"http://{self.host}:{self.port}/{self.identifier}/get/{self.ID}"

            response = requests.get(url)
            response.raise_for_status()
            response_json = response.json()
            status = response_json["status"]

            if QueueStatus(status) == QueueStatus.Cancelled:
                sucess = True
                break

            time.sleep(3)

        if not sucess:
            raise Exception("Could not stop job")

        print("Stopped",self.ID)

    def start(self):
        assert self.ID is None, "Already started"
        
        if not self.host:
            self.host, self.port = self._get_addr_for_job(self.identifier)

        input_data = replace_paths_with_strings(self.input_data)

        url = f"http://{self.host}:{self.port}/{self.identifier}/file_keys"
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
        url = f"http://{self.host}:{self.port}/{self.identifier}/new"
        print(f"Creating new job on {self.host}:{self.port}")
        response = requests.post(url, json=input_data_not_files)
        response.raise_for_status()
        self.ID = response.json()

        ## Upload the files

        for key, value in input_data_files.items():
            url = f"http://{self.host}:{self.port}/{self.identifier}/upload/{self.ID}"
            with open(value, "rb") as f:
                print(f"Uploading file to {self.host}:{self.port}:", key, ":", value, )
                files = {"file": f}
                data = {"key": key}
                response = requests.post(url, files=files, data=data)
                response.raise_for_status()

        ## RUN The thing

        #data = {"test": "hejsa"}
        print(data)
        print(f"Starting job on {self.host}:{self.port} with ID:", self.ID)
        url = f"http://{self.host}:{self.port}/{self.identifier}/start/{self.ID}"
        response = requests.post(url, json=self.job.dict())
        response.raise_for_status()
        
        print(self.identifier,"job submitted with ID:", self.ID, "to", self.host)

    def wait_for_finish(self):

        assert self.ID is not None, "Not started"
        if self.strict_output_dir:
            output_path = self.output_directory
        else:
            output_path = _create_output_directory(self.output_directory,self.identifier)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        output = None
        while output is None:
            url = f"http://{self.host}:{self.port}/{self.identifier}/get/{self.ID}"

            response = requests.request("GET", url, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            status = response_json["status"]
            if QueueStatus(status) == QueueStatus.Finished:
                break
            elif QueueStatus(status) == QueueStatus.Error:
                raise Exception("The job exited with an error: "+response_json["error"]["traceback"])
            elif QueueStatus(status) == QueueStatus.Cancelled:                raise Exception("The job was cancelled")
            elif QueueStatus(status) == QueueStatus.Queued:
                time.sleep(10)
            elif QueueStatus(status) == QueueStatus.Running:
                time.sleep(4)

        url = f"http://{self.host}:{self.port}/{self.identifier}/get2/{self.ID}"
        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()
        output = response.json()
        for key, value in output.items():
            if isinstance(value, str):
                if value.startswith(f"/{self.identifier}/download/"):
                    print("Downloading", key, "...")
                    url = f"http://{self.host}:{self.port}/{self.identifier}/download/{self.ID}/{key}"

                    response = requests.get(url)
                    response.raise_for_status()
                    fname = response.headers['Content-Disposition'].split('=')[1].replace('"','')
                    fname = Path(os.path.join(output_path,fname)).absolute()
                    with open(fname, 'wb') as f:
                        f.write(response.content)
                    output[key] = fname
        
        return output


def replace_paths_with_strings(inp):
    if isinstance(inp, BaseModel):
        inp = inp.dict()
    for key, val in inp.items():
        if isinstance(val, Path):
            inp[key] =  str(val)
        else:
            inp[key] = val
    return inp


def _create_output_directory(base_directory, node_name):
    directory = os.path.join(base_directory, node_name)
    i = 1
    while True:
        if not os.path.exists(directory):
            break
        directory = os.path.join(base_directory, node_name + "_" + str(i))
        i += 1
    os.makedirs(directory)
    return directory