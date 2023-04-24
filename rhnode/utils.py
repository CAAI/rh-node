from pathlib import Path
import requests
from enum import Enum
import uuid
from pydantic import BaseModel, DirectoryPath
import time
import os 
from typing import Union

class Job(BaseModel):
    id: str
    device: Union[None, int]
    check_cache: bool = True
    save_to_cache: bool = True
    priority: int = 2
    directory: Union[None, DirectoryPath] = None

class QueueStatus(Enum):
    Preparing= -1
    Initializing = 0
    Queued = 1
    Running = 2
    Finished = 3
    Error = 4

def GET_HOST_FOR_JOB(node):
    headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
    }
    url = f"http://manager:8000/dispatcher/get_host/{node}"
    response = requests.request("GET", url, headers=headers)
    
    # Check for errors
    response.raise_for_status()
    
    # Parse the response JSON
    host = response.json()

    #FIX THIS
    port = 8000
    return host, port

def new_job(check_cache = True, save_to_cache = True,priority = 2):
    uid = str(uuid.uuid4())
    job = Job(id=uid,
        device = None,
        check_cache = check_cache,
        save_to_cache = save_to_cache,
        directory=None,
        priority = priority)
    return job



class NodeRunner:

    def __init__(self, identifier, inputs, job, port = None, host=None,use_same_gpu=False,output_directory=None):
        self.identifier = identifier
        self.input_data = inputs.copy()
        self.job = job.copy()
        self.port = port
        self.ID = None
        self.host = host
        self.use_same_gpu = use_same_gpu
        if output_directory is None:
            if job.directory is None:
                output_directory = "./output"
            else:
                output_directory = job.directory

        self.output_directory = output_directory
        if (port is None ) ^ (host is None):
            raise Exception("Specify both port and host or neither")

    def start(self):
        assert self.ID is None, "Already started"
        if not self.host:
            self.host = GET_HOST_FOR_JOB(self.identifier)

        # Set the headers for the request
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        input_data = replace_paths_with_strings(self.input_data)


        ## Get file keys

        url = f"http://{self.host}:{self.port}/file_keys"
        response = requests.request("GET", url, headers=headers)
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
        url = f"http://{self.host}:{self.port}/new"
        print(f"Creating new job on {self.host}:{self.port}")
        response = requests.request("POST", url, headers=headers, json=input_data_not_files)
        response.raise_for_status()
        self.ID = response.json()

        ## Upload the files

        for key, value in input_data_files.items():
            url = f"http://{self.host}:{self.port}/upload/{self.ID}"
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
        url = f"http://{self.host}:{self.port}/start/{self.ID}"
        response = requests.request("POST", url, headers=headers, json=self.job.dict())
        response.raise_for_status()
        
        print(self.identifier,"job submitted with ID:", self.ID, "to", self.host)

    def wait_for_finish(self):

        assert self.ID is not None, "Not started"
        output_path = _create_output_directory(self.output_directory,self.identifier)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        output = None
        while output is None:
            url = f"http://{self.host}:{self.port}/get/{self.ID}"
            response = requests.request("GET", url, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            status = response_json["status"]
            if QueueStatus(status) == QueueStatus.Finished:
                break
            elif QueueStatus(status) == QueueStatus.Error:
                raise Exception("Error in queue")
            else:
                time.sleep(2)

        url = f"http://{self.host}:{self.port}/get2/{self.ID}"
        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()
        output = response.json()
        for key, value in output.items():
            if isinstance(value, str):
                if value.startswith("/download/"):
                    print("Downloading", key, "...")
                    url = f"http://{self.host}:{self.port}/download/{self.ID}/{key}"

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