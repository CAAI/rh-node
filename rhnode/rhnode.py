import multiprocessing
from abc import ABC, abstractmethod
from pydantic import BaseModel, FilePath
import requests
import asyncio
import uuid
from .cache import Cache
from .rhjob import *
from .common import *
from fastapi.responses import FileResponse
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from .rhprocess import RHProcess
from .frontend import setup_frontend_routes
import traceback
import datetime

MANAGER_URL = "http://manager:8000/manager"


class RHNode(ABC, FastAPI):
    """Base class for RHNode. All custom nodes should inherit from this class"""

    input_spec: BaseModel
    output_spec: BaseModel
    name: str
    cache_size = 3
    requires_gpu = True
    cache_directory = ".cache"
    output_directory = ".outputs"  # Where the output files are stored for each job
    input_directory = ".inputs"  # Where the input files are stored for each job

    required_gb_gpu_memory = None
    required_num_threads = None
    required_gb_memory = None

    def __init__(self):
        super().__init__(
            docs_url="/" + self.name + "/docs",
            openapi_url="/" + self.name + "/api/openapi.json",
        )

        self.cache = Cache(
            self.cache_directory, self.output_spec, self.input_spec, self.cache_size
        )

        # Effectively the "database" of the node
        self.jobs = {}

        # Create variants of input and output spec for different stages of the job
        self.output_spec_url = create_filepath_as_string_model(self.output_spec)
        self.input_spec_no_file = create_model_no_files(self.input_spec)

        # A list of the input keys of FilePath type.
        self.file_keys = [
            key
            for key, val in self.input_spec.__fields__.items()
            if val.type_ == FilePath
        ]

        self.setup_api_routes()
        setup_frontend_routes(self)

    def _delete_job(self, job_id):
        pass
        job = self.jobs[job_id]
        job.delete_files()
        del self.jobs[job_id]

    def _get_expired_job_ids(self, max_age_hours=8):
        """Get a list of job IDs that have been in the queue for longer than max_age_hours"""
        expired_job_ids = []
        for job_id, job in self.jobs.items():
            if (time.time() - job.time_created) / 3600 > max_age_hours:
                if job.status in [
                    JobStatus.Finished,
                    JobStatus.Error,
                    JobStatus.Cancelled,
                ]:
                    expired_job_ids.append(job_id)

        return expired_job_ids

    async def _delete_expired_jobs_loop(
        self, hour: int = 3, minute: int = 30, second: int = 0
    ):
        print("Starting daily task to delete expired jobs")
        while True:
            now = datetime.datetime.now()

            # Set the time for the next task run
            next_run = datetime.datetime.combine(
                now.date(), datetime.time(hour, minute, second)
            )

            # If the time has already passed for today, schedule it for tomorrow
            if now.time() > datetime.time(hour, minute, second):
                next_run += datetime.timedelta(days=1)

            delay = (next_run - now).total_seconds()
            print("Next check in", delay, "seconds")
            await asyncio.sleep(delay)
            print("Checking for expired jobs...")
            jobs = self._get_expired_job_ids()
            for job_id in jobs:
                print("Deleting job", job_id)
                self._delete_job(job_id)

    def CREATE_JOB(self, input_spec_no_file):
        """Create a job (named RHProcess as not to conflict with RHJob).
        See rhprocess.py for more details."""

        # Generate a unique ID for the job
        while (ID := str(uuid.uuid4())) in self.jobs.keys():
            continue

        # Standard job arguments
        default_job_args = {
            "required_gb_gpu_memory": self.required_gb_gpu_memory,
            "required_num_threads": self.required_num_threads,
            "required_gb_memory": self.required_gb_memory,
            "target_function": self.__class__.process_wrapper,
            "manager_endpoint": MANAGER_URL,
            "input_spec": self.input_spec,
            "output_spec": self.output_spec,
            "cache": self.cache,
            "name": self.name,
        }

        # Create the job, and store it in the jobs dictionary
        job = RHProcess(
            inputs_no_files=input_spec_no_file,
            ID=ID,
            output_directory=Path(self.output_directory) / ID,
            input_directory=Path(self.input_directory) / ID,
            **default_job_args,
        )

        self.jobs[ID] = job
        return ID

    async def _register_with_manager(self):
        """Try to register the node with the manager. This is called at startup."""

        success = False
        for _i in range(5):
            print("Trying to register with manager")
            try:
                url = MANAGER_URL + "/register_node"
                node = NodeMetaData(
                    name=self.name,
                    last_heard_from=0,
                    gpu_gb_required=self.required_gb_gpu_memory,
                    memory_required=self.required_gb_memory,
                    threads_required=self.required_num_threads,
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
        """Create a URL for the node, with the node name as a prefix."""
        assert url.startswith("/") or url == ""
        return "/" + self.name + url

    def _get_output_with_download_links(self, job_id):
        """Get the output of a finished job, with download links for any FilePath fields."""
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
        """Setup the API routes for the node. See frontend.py for the frontend routes."""

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
            return "OK"

        @self.get(self._create_url("/jobs/{job_id}/status"))
        async def _get_job_status(job_id: str) -> JobStatus:
            return self.jobs[job_id].status

        @self.get(self._create_url("/jobs/{job_id}/data"))
        async def _get_job_data_download_urls(job_id: str) -> self.output_spec_url:
            return self._get_output_with_download_links(job_id)

        @self.get(self._create_url("/jobs/{job_id}/error"))
        def _get_job_error(job_id: str):
            return self.jobs[job_id].error

        @self.post(self._create_url("/jobs/{job_id}/stop"))
        def _stop_task(job_id: str):
            self.jobs[job_id].stop()
            return "OK"

        @self.post(self._create_url("/jobs/{job_id}/delete"))
        async def _delete_job(job_id: str):
            """Delete a job from the node."""
            self._delete_job(job_id)

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
            """Upload an input file to a job. The key must be one of the file keys."""
            assert key in self.file_keys
            job = self.jobs[job_id]

            # The outer with statement is to ensure that the file is validated after upload
            with job.upload_file(key, file.filename) as fpath:
                with open(fpath, "wb") as f:
                    f.write(await file.read())

            return "OK"

        ### OTHER
        @self.on_event("startup")
        async def register_on_startup():
            # print(multiprocessing.get_start_method())
            """Looks for manager node at startup and initializes multiprocessing module"""
            # if not os.environ.get("PYTEST", False):
            multiprocessing.set_start_method("spawn")
            asyncio.create_task(self._register_with_manager())

        @self.on_event("startup")
        async def start_cleaning_loop():
            asyncio.create_task(self._delete_expired_jobs_loop())

    @classmethod
    def process_wrapper(cls, inputs, job, result_queue):
        """Wrapper for the process function. It has two purposes: catching errors and packing the output of the process function into the "queue" object."""
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
