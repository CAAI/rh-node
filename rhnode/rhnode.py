import multiprocessing
import time
from abc import ABC, abstractmethod
from pydantic import BaseModel, FilePath, DirectoryPath
from fastapi import APIRouter
import os
from pathlib import Path
import requests
import asyncio
from fastapi import BackgroundTasks
import uuid
from enum import Enum
from .cache import Cache
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, PackageLoader
from contextlib import asynccontextmanager
from .utils import QueueStatus, Job
from multiprocessing import Process
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from typing import Type, Dict
from pydantic import create_model, BaseModel, FilePath
from fastapi import FastAPI, File, UploadFile
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel, Field
from typing import BinaryIO, Optional, Union
from fastapi import FastAPI, File, Form, UploadFile

class FileField(BinaryIO):
    """A subclass of BinaryIO that represents a file upload field."""

def create_filepath_as_string_model(cls: Type[BaseModel]) -> Type[BaseModel]:
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            fields[field_name] = (str, field.field_info)
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "URL", **fields, __base__=cls)

def create_relaxed_filepath_model(cls: Type[BaseModel]) -> Type[BaseModel]:
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            fields[field_name] = (Union[None,FilePath], field.field_info)
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "RELAX", **fields, __base__=cls)


def create_model_no_files(cls: Type[BaseModel]) -> Type[BaseModel]:
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            continue
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "INIT", **fields)


# Define a Jinja2 environment that can load templates from a package

env = Environment(loader=PackageLoader(__name__, 'resources/templates'))
templates = Jinja2Templates(directory="resources/templates")

class QueueResponse(BaseModel):
    status: QueueStatus #Waiting for GPU, Running, Finished, Error
    output: BaseModel = None
    input: BaseModel = None
    input_directory: DirectoryPath = None

class RHNode(ABC, FastAPI):
    
    #make input_spec required
    input_spec: BaseModel
    output_spec: BaseModel
    name: str
    cache_size = 3
    requires_gpu = True
    cache_directory = "./.cache"
    task_directory = "./.tasks"
    input_directory = "./.inputs"
    def __init__(self):
        super().__init__()

        self.cache = Cache(self.cache_directory, self.output_spec, self.input_spec,self.cache_size)
        
        self.task_status = {
        }

        self.output_spec_url = create_filepath_as_string_model(self.output_spec)
        self.input_spec_no_file = create_model_no_files(self.input_spec)
        self.input_spec_optional_file = create_relaxed_filepath_model(self.input_spec)


        self.setup_routes()
    # def receive_rhserver_handle(self, RHServer):
    #     self.RHServer = RHServer


    def get_queue_status(self,queue_id):
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"http://manager:8000/queue/status/{queue_id}"
        response = requests.request("GET", url, headers=headers)

        # Check for errors
        response.raise_for_status()

        # Parse the response JSON
        queue_status = response.json()
        return queue_status

    def queue_cuda_job(self):
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"http://manager:8000/queue/add"
        response = requests.request("GET", url, headers=headers)

        # Check for errors
        response.raise_for_status()

        # Parse the response JSON
        queue_id = response.json()
        return queue_id


    def release_cuda_job(self,queue_id):
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"http://manager:8000/queue/remove/{queue_id}"
        response = requests.request("GET", url, headers=headers)

        # Check for errors
        response.raise_for_status()

        # Parse the response JSON
        queue_id = response.json()
        return queue_id
    
    @asynccontextmanager
    async def maybe_wait_for_cuda_device(self,job):
        
        queue_id = None
        if job.device is not None:
            yield job.device
        
        elif not self.requires_gpu:
            yield None
        else:
            print("Getting into CUDA queue...")

            queue_id = self.queue_cuda_job()

            while gpu_id:=self.get_queue_status(queue_id) is None:
                await asyncio.sleep(3)

            try:
                yield gpu_id
            finally:
                if queue_id:
                    self.release_cuda_job(queue_id)
    
    def _cleanup_output_directory(self, directory, outputs):
        out_files = []
        for key,val in outputs.dict(exclude_unset=True).items():
            if self.output_spec.__fields__[key].type_ == FilePath:
                out_files.append(str(Path(val).absolute()))
                
        # Remove all files not in outputs
        for root, dirs, files in os.walk(directory):
            for file in files:
                fpath = Path(root,file).absolute()
                if str(fpath) not in out_files:
                    os.remove(fpath)
        
        # Remove all empty directories
        for root, dirs, files in os.walk(directory,topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)


    def _cleanup_input_directory(self, directory):
        out_files = []
        assert directory.startswith(self.input_directory)
        for file in os.listdir(directory):
            fpath = Path(directory,file).absolute()
            os.remove(fpath)
        

    def _make_input_directory(self, task_id):
        new_dir = self.input_directory + "/" + task_id
        os.makedirs(new_dir)
        return new_dir

    def _make_job_directory(self, task_id):
        new_dir = self.task_directory + "/" + task_id
        os.makedirs(new_dir)
        return new_dir
        
    def process_wrapper(self, inputs,job,result_queue):
        response = self.__class__.process(inputs,job)
        result_queue.put(response)

    async def run(self, job, task_id):
        new_dir = self._make_job_directory(task_id)
        job.directory = Path(new_dir)
        inputs = self.get_task_data(task_id).input
        cache_key = self.cache._get_cache_key(inputs)

        if job.check_cache and self.cache._result_is_cached(cache_key):
            response = self.cache._load_from_cache(cache_key,job.directory)
            self._set_task_data(task_id, QueueStatus.Finished, response)
            return 
        
        self._set_task_data(task_id, QueueStatus.Queued, None)

        async with self.maybe_wait_for_cuda_device(job) as cuda_device:
            
            #Check cache again just for good measures
            if job.check_cache and self.cache._result_is_cached(cache_key):
                response = self.cache._load_from_cache(cache_key,job.directory)
                self._set_task_data(task_id, QueueStatus.Finished, response)
                return 

            job.device = cuda_device
            self._set_task_data(task_id, QueueStatus.Running, None)
            result_queue = multiprocessing.Queue()
            p = Process(target= self.process_wrapper,args = (inputs,job,result_queue))
            p.start()
            while p.is_alive():
                await asyncio.sleep(3)
        
        response = result_queue.get()
        self._cleanup_output_directory(job.directory, response)
        self._cleanup_input_directory(self.get_task_data(task_id).input_directory)
        if job.save_to_cache:
            self.cache._save_to_cache(cache_key, response, job.directory)
        
        self._set_task_data(task_id, QueueStatus.Finished, response)
        return response
    
    def get_task_data(self, task_id):
        return self.task_status[task_id]
    
    def _set_task_data(self, task_id, status, output):
        self.task_status[task_id].status = status
        self.task_status[task_id].output = output

    def _delete_task_data(self,task_id):
        del self.task_status[task_id]

    def _get_keys_for_files(self):
        keys = []

        for key,val in self.input_spec.__fields__.items():
            if val.type_ == FilePath:
                keys.append(key)

        return keys


    def _new_task(self,input_spec_no_file):
        task_id = str(uuid.uuid4())
        directory = self._make_input_directory(task_id)
        input_optional = self.input_spec_optional_file(**input_spec_no_file.dict())
        self.task_status[task_id] = QueueResponse(status=QueueStatus.Preparing, output=None,input=input_optional,input_directory=directory)
        return task_id
    

    def _set_task_initializing(self,task_id):
        assert self.task_status[task_id].status == QueueStatus.Preparing
        new_input = self.input_spec(**self.task_status[task_id].input.dict())
        self.task_status[task_id].input = new_input

    
    def _get_default_context(self):         
        return {
            "node_name":self.name,
        }
    
    def _create_file_name_from_key(self, output_name, file_name):
        if "." in os.path.basename(file_name):
            ending = os.path.basename(file_name).split(".")[1:]
            ending = ".".join(ending)
            return f"{output_name}.{ending}"
        return output_name
    
    def _fix_output(self, output):
        outs = []
        for key, val in output.dict(exclude_unset=False).items():
            dat = {}
            dat["name"] = key
            dat["val"] = val
            if isinstance(val,str):
                if val.startswith("/download/"):
                    dat["val"] = "download"
                    dat["href"] = val
            outs.append(dat)
        return outs 
    

    def _get_with_download_links(self, queue_id):
        task = self.get_task_data(queue_id)

        new_d = {}
        for key,val in task.output.dict(exclude_unset=True).items():
            if self.output_spec.__fields__[key].type_ == FilePath:
                new_d[key] = self.url_path_for("_get_file",queue_id=queue_id,filename=key)
            else:
                new_d[key] = val

        return self.output_spec_url(**new_d)

    def setup_routes(self):

        class GetResponse(BaseModel):
            status: QueueStatus #Waiting for GPU, Running, Finished, Error
            output: self.output_spec = None

        @self.post("/new")
        async def _run(inputs: self.input_spec_no_file) -> str:
            task_id = self._new_task(inputs)
            return task_id

        @self.post("/start/{task_id}")
        async def _run(task_id: str, job:Job, background_tasks: BackgroundTasks) -> str:
            self._set_task_initializing(task_id)
            background_tasks.add_task(self.run, job, task_id)
            return "lol"
        
        @self.get("/get/{queue_id}")
        async def _get(queue_id:str) -> GetResponse:
            return self.get_task_data(queue_id)
        

        @self.get("/get2/{queue_id}")
        async def _get2(queue_id:str) -> self.output_spec_url:
            return self._get_with_download_links(queue_id)
        
        @self.get("/show/{queue_id}", response_class=HTMLResponse)
        async def _show(queue_id:str) -> HTMLResponse:
            task = self.get_task_data(queue_id)
            output = None
            if task.status == QueueStatus.Finished:
                output = self._get_with_download_links(queue_id)
                output = self._fix_output(output)
            
            template = env.get_template('task.html')
            
            html_content = template.render(
                default_context=self._get_default_context(),
                outputs=output,
                queue_status=task.status,
                queue_id = queue_id
            )

            return html_content
                
        @self.get("/download/{queue_id}/{filename}")
        def _get_file(queue_id, filename):
            print(queue_id,filename)
            fname = self.get_task_data(queue_id).output.dict()[filename]
            return FileResponse(fname,filename=self._create_file_name_from_key(filename,fname))

        @self.get("/", response_class=HTMLResponse)
        async def show_task_status(request: Request):
            # Load the template from the package
            template = env.get_template('task_status.html')
            formats = []
            for task_id, task in self.task_status.items():
                formats.append(
                    {
                        "task_id": task_id,
                        "status": task.status,
                        "href": self.url_path_for("_show",queue_id=task_id)
                    }
                )
            html_content = template.render(
                default_context=self._get_default_context(),
                tasks=formats
            )

            # Return the rendered webpage
            return html_content
        @self.get("/file_keys")
        async def _get_file_keys():
            return self._get_keys_for_files()

        @self.post("/upload/{task_id}")
        async def _upload(
            task_id: str,
            file: UploadFile = File(...),
            key: str =  Form(...),
            ):

            
            assert key in self.input_spec.__fields__
            assert self.input_spec.__fields__[key].type_ == FilePath

            task_data = self.get_task_data(task_id)
            filename = self._create_file_name_from_key(key,file.filename)
            with open(task_data.input_directory / filename, "wb") as f:
                f.write(await file.read())
            task_data.input = task_data.input.copy(update={key: task_data.input_directory / filename})
            return {"status": "Files uploaded successfully"}

        self.mount("/static", StaticFiles(directory=os.path.dirname(__file__)+"/resources/static"), name="static")
        
        @staticmethod   
        @abstractmethod
        def process(inputs, job):
            pass



