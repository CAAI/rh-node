import multiprocessing
from abc import ABC, abstractmethod
from pydantic import BaseModel, FilePath
import requests
import asyncio
import uuid
from .cache import Cache
from .utils import *
from .common import *
from fastapi.responses import FileResponse

from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from .jobs import Job
from .frontend import setup_frontend_routes
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from datetime import time

MANAGER_URL = "http://manager:8000/manager"

# Define a Jinja2 environment that can load templates from a package


class RHNode(ABC, FastAPI):
    # make input_spec required
    input_spec: BaseModel
    output_spec: BaseModel
    name: str
    cache_size = 3
    requires_gpu = True
    cache_directory = ".cache"
    task_directory = ".tasks"
    input_directory = ".inputs"

    required_gb_gpu_memory = None
    required_num_processes = None
    required_gb_memory = None

    def __init__(self):
        super().__init__(
            docs_url="/" + self.name + "/docs",
            openapi_url="/" + self.name + "/api/openapi.json",
        )

        self.cache = Cache(
            self.cache_directory, self.output_spec, self.input_spec, self.cache_size
        )

        self.jobs = {}
        self.output_spec_url = create_filepath_as_string_model(self.output_spec)
        self.input_spec_no_file = create_model_no_files(self.input_spec)
        self.file_keys = [
            key
            for key, val in self.input_spec.__fields__.items()
            if val.type_ == FilePath
        ]

        self.default_job_args = {
            "required_gb_gpu_memory": self.required_gb_gpu_memory,
            "required_num_processes": self.required_num_processes,
            "required_gb_memory": self.required_gb_memory,
            "target_function": self.__class__.process_wrapper,
            "manager_endpoint": MANAGER_URL,
            "input_spec": self.input_spec,
            "output_spec": self.output_spec,
            "cache": self.cache,
            "name": self.name,
        }

        self.setup_api_routes()
        setup_frontend_routes(self)

        self.scheduler = AsyncIOScheduler()

        # Schedule your task to run at 4am every day
        self.scheduler.add_job(self._remove_old_jobs, "cron", hour=4, minute=0)

        # Start the scheduler
        self.scheduler.start()

    def _remove_old_jobs(self):
        current_time = time.time()
        to_remove = []

        for job_id, job in self.jobs.items():
            delta_hours = (current_time - job.time_created) / 3600
            if delta_hours > 4:
                job.delete()

    def CREATE_JOB(self, input_spec_no_file):
        while (ID := str(uuid.uuid4())) in self.jobs.keys():
            continue
        job = Job(
            inputs_no_files=input_spec_no_file,
            ID=ID,
            output_directory=Path(self.task_directory) / ID,
            input_directory=Path(self.input_directory) / ID,
            **self.default_job_args,
        )

        self.jobs[ID] = job
        return ID

    async def _register_with_manager(self):
        success = False
        for i in range(5):
            print("Trying to register with manager")
            try:
                url = MANAGER_URL + "/register_node"
                node = Node(
                    name=self.name,
                    last_heard_from=0,
                    gpu_gb_required=self.required_gb_gpu_memory,
                    memory_required=self.required_gb_memory,
                    cores_required=self.required_num_processes,
                )
                response = requests.post(url, json=node.dict())
                response.raise_for_status()
                success = True
                break
            except:
                await asyncio.sleep(2)
        if not success:
            print("Could not register with manager")
        else:
            print("Registered with manager")

    def _create_url(self, url):
        assert url.startswith("/") or url == ""
        return "/" + self.name + url

    def _get_output_with_download_links(self, job_id):
        job = self.jobs[job_id]
        return self.output_spec_url(
            **{
                key: self.url_path_for("_get_file", job_id=job_id, filename=key)
                if self.output_spec.__fields__[key].type_ == FilePath
                else val
                for key, val in job.output.dict(exclude_unset=True).items()
            }
        )

    def setup_api_routes(self):
        @self.post(self._create_url("/jobs"))
        async def _post_new_job(inputs: self.input_spec_no_file) -> str:
            job_id = self.CREATE_JOB(inputs)
            return job_id

        @self.post(self._create_url("/jobs/{job_id}/start"))
        async def START_JOB(
            job_id: str, job: JobMetaData, background_tasks: BackgroundTasks
        ) -> str:
            job_obj = self.jobs[job_id]
            background_tasks.add_task(job_obj.run, job)
            return "ok"

        @self.get(self._create_url("/jobs/{job_id}/status"))
        async def _get_job_status(job_id: str) -> QueueStatus:
            return self.jobs[job_id].status

        @self.get(self._create_url("/jobs/{job_id}/data"))
        async def _get_job_data_download_urls(job_id: str) -> self.output_spec_url:
            return self._get_output_with_download_links(job_id)

        @self.get(self._create_url("/jobs/{job_id}/error"))
        def _get_job_error(job_id: str):
            return self.jobs[job_id].error

        @self.post(self._create_url("/jobs/{job_id}/stop"))
        def _remove_task(job_id: str):
            self.jobs[job_id].stop()
            return "OK"

        @self.get(self._create_url("/jobs/{job_id}/download/{filename}"))
        def _get_file(job_id, filename):
            fname = self.jobs[job_id].output.dict()[filename]
            return FileResponse(
                fname, filename=create_file_name_from_key(filename, fname)
            )

        @self.get(self._create_url("/filename_keys"))
        async def _get_file_keys():
            return self.file_keys

        @self.post(self._create_url("/jobs/{job_id}/upload"))
        async def _upload(
            job_id: str,
            file: UploadFile = File(...),
            key: str = Form(...),
        ):
            assert key in self.file_keys
            job = self.jobs[job_id]
            with job.upload_file(key, file.filename) as fpath:
                with open(fpath, "wb") as f:
                    f.write(await file.read())

            return "OK"

        ### OTHER
        @self.on_event("startup")
        async def register_on_startup():
            """Looks for manager node at startup and initializes multiprocessing module"""
            multiprocessing.set_start_method("spawn")
            asyncio.create_task(self._register_with_manager())

    @classmethod
    def process_wrapper(cls, inputs, job, result_queue):
        try:
            response = cls.process(inputs, job)
            result_queue.put(("success", response))
        except Exception as e:
            tb_str = traceback.format_exception(type(e), value=e, tb=e.__traceback__)
            result_queue.put(("error", tb_str, str(type(e))))

    @staticmethod
    @abstractmethod
    def process(inputs, job):
        pass
