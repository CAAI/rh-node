import multiprocessing
from pydantic import FilePath
import os
from pathlib import Path
import requests
import asyncio
from contextlib import asynccontextmanager
from .rhjob import JobStatus, QueueRequest
from multiprocessing import Process
import traceback
from .common import *
from contextlib import contextmanager
import time


class RHProcess:
    """Each "job" corresponds to one instance of this class.
    This class is responsible for running the process function of the node,
    communicating with the resource queue, and handling IO"""

    def __init__(
        self,
        output_directory,
        input_directory,
        inputs_no_files,
        required_gb_gpu_memory,
        required_num_threads,
        required_gb_memory,
        ID,
        input_spec,
        output_spec,
        cache,
        target_function,
        name,
        manager_endpoint=None,
    ):
        self.target_function = target_function
        self.status = None
        self.error = None
        self.time_created = time.time()
        self.time_last_accessed = None
        self.output = None
        self.input = inputs_no_files

        self.output_directory = output_directory
        self.input_directory = input_directory
        self.required_gb_gpu_memory = required_gb_gpu_memory
        self.required_num_threads = required_num_threads
        self.required_gb_memory = required_gb_memory
        self.manager_endpoint = manager_endpoint
        self.ID = ID
        self.input_spec = input_spec
        self.output_spec = output_spec
        self.input_spec_optional_file = create_relaxed_filepath_model(self.input_spec)
        self.cache = cache
        self.name = name
        self.status = JobStatus.Preparing

        self._make_input_directory()

    ## IO
    def _cleanup_output_directory(self, response):
        out_files = []
        for key, val in response.dict(exclude_unset=True).items():
            if self.output_spec.__fields__[key].type_ == FilePath:
                out_files.append(str(Path(val).absolute()))

        # Remove all files not in outputs
        for root, dirs, files in os.walk(self.output_directory):
            for file in files:
                fpath = Path(root, file).absolute()
                if str(fpath) not in out_files:
                    os.remove(fpath)

        # Remove all empty directories
        for root, dirs, files in os.walk(self.output_directory, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)

    def _remove_input_directory(self):
        for file in os.listdir(self.input_directory):
            fpath = Path(self.input_directory, file).absolute()
            os.remove(fpath)
        os.rmdir(self.input_directory)

    def _remove_output_directory(self):
        for file in os.listdir(self.output_directory):
            fpath = Path(self.output_directory, file).absolute()
            os.remove(fpath)

        os.rmdir(self.output_directory)

    def _make_input_directory(self):
        new_dir = os.path.join(self.input_directory)
        os.makedirs(new_dir)
        return new_dir

    def _make_job_directory(self):
        new_dir = os.path.join(self.output_directory)
        os.makedirs(new_dir)
        return new_dir

    ## QUEUING
    def _get_queue_status(self, queue_id: str):
        url = self.manager_endpoint + f"/is_job_active/{queue_id}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def _queue(self, job):
        url = self.manager_endpoint + f"/add_job"
        queue_id = self.name + "_" + self.ID
        jobreq = QueueRequest(
            job_id=queue_id,
            priority=job.priority,
            required_gpu_mem=self.required_gb_gpu_memory,
            required_threads=self.required_num_threads,
            required_memory=self.required_gb_memory,
        )
        response = requests.post(url, json=jobreq.dict())
        response.raise_for_status()
        return queue_id

    def _release_job_resources(self, queue_id):
        url = self.manager_endpoint + f"/end_job/{queue_id}"
        response = requests.post(url)
        response.raise_for_status()
        return response.json()

    @asynccontextmanager
    async def _maybe_wait_for_resources(self, job):
        queue_id = None
        if job.resources_included:
            yield job.device

        else:
            print("Entering resource queue...")
            queue_id = self._queue(job)
            gpu_id = None
            while True:
                status = self._get_queue_status(queue_id)
                if status["is_active"]:
                    gpu_id = status["gpu_device_id"]
                    break
                ## If the task is cancelled yield None
                ## THe run function will check for the status and not spawn the process
                if self.status == JobStatus.Cancelling:
                    self.status = JobStatus.Cancelled
                    gpu_id = None
                    break

                await asyncio.sleep(3)
            try:
                yield gpu_id
            finally:
                if queue_id:
                    self._release_job_resources(queue_id)

    ## Job file and directory management
    def _validate_and_maybe_fix_response(self, response):
        """
        Checks is all FilePaths are in the correct directory and changes absolute
        filepaths to relative paths and PosixPath for consistency
        """
        new_d = {}
        output_dir = Path(self.output_directory)

        for key, val in response.dict(exclude_unset=True).items():
            if self.output_spec.__fields__[key].type_ == FilePath:
                val = Path(val)

                if is_relative_to(val, output_dir):
                    new_d[key] = val

                # Check if the path is an absolute path and lies within the .task folder
                elif val.is_absolute() and is_relative_to(val, output_dir.absolute()):
                    new_d[key] = val.relative_to(Path.cwd())

                else:
                    raise Exception(
                        f"File path {val} is not inside the job output folder {output_dir}"
                    )
            else:
                new_d[key] = val

        return self.output_spec(**new_d)

    ## JOB RUNNING
    async def run(self, job):
        assert self.status == JobStatus.Preparing
        self.input = self.input_spec(**self.input.dict())

        ## Cancel signal might come before the run function is called executes
        if self.status == JobStatus.Cancelling:
            self.statis = JobStatus.Cancelled
            return

        new_dir = self._make_job_directory()
        job.directory = Path(new_dir)
        cache_key = self.cache._get_cache_key(self.input)

        if job.check_cache and self.cache._result_is_cached(cache_key):
            response = self.cache._load_from_cache(cache_key, job.directory)
            self.status = JobStatus.Finished
            self.output = response
            return

        self.status = JobStatus.Queued

        async with self._maybe_wait_for_resources(job) as cuda_device:
            ## Cancel signal might come in waiting for cuda queue
            if self.status == JobStatus.Cancelled:
                return

            # Check cache again just for good measures
            if job.check_cache and self.cache._result_is_cached(cache_key):
                response = self.cache._load_from_cache(cache_key, job.directory)
                self.status = JobStatus.Finished
                self.output = response
                return

            job.device = cuda_device
            self.status = JobStatus.Running
            result_queue = multiprocessing.Queue()
            p = Process(
                target=self.target_function,
                args=(self.input.copy(), job.copy(), result_queue),
            )
            p.start()
            while p.is_alive():
                if self.status == JobStatus.Cancelling:
                    p.terminate()
                    while p.is_alive():
                        print("Waiting for process to terminate...")
                        await asyncio.sleep(0.5)
                    result_queue.put(("cancelled", "Task was cancelled while running"))
                    break
                await asyncio.sleep(3)

        response = result_queue.get()
        if response[0] == "error":
            error_message = "".join(response[1])
            error_type = response[2]
            print(f"The Process ended with an error: {error_message}")

            self.status = JobStatus.Error
            self.error = Error(traceback=error_message, error=error_type)

        elif response[0] == "cancelled":
            print(f"The Process was cancelled")
            self.status = JobStatus.Cancelled
        else:
            response = response[1]
            response = self._validate_and_maybe_fix_response(response)
            self._cleanup_output_directory(response)
            self._remove_input_directory()
            if job.save_to_cache:
                self.cache._save_to_cache(cache_key, response, job.directory)
            self.status = JobStatus.Finished
            self.output = response

    @contextmanager
    def upload_file(self, file_key, in_filename):
        filename = create_file_name_from_key(file_key, in_filename)
        file_path = self.input_directory / filename
        yield file_path

        assert os.path.isfile(file_path)
        self.input = self.input.copy(update={file_key: self.input_directory / filename})

    def delete(self):
        self._remove_output_directory()

    def stop(self):
        if self.status in [
            JobStatus.Finished,
            JobStatus.Cancelled,
            JobStatus.Error,
            JobStatus.Cancelling,
        ]:
            raise Exception(
                "Task cannot be cancelled when it has status: ",
                self.status,
            )
        self.status = JobStatus.Cancelling
