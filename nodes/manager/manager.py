import heapq
import requests
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
import os
import socket
from fastapi import FastAPI, HTTPException
from fastapi.templating import Jinja2Templates
from rhnode.common import QueueRequest, NodeMetaData
from dotenv import load_dotenv
from rhnode.version import __version__
import time
from pydantic import BaseModel, validator

# load env variables from .env file if it exists
load_dotenv()


class Job(BaseModel):
    priority: int
    ID: str
    required_gpu_mem: int
    required_memory: int
    required_threads: int
    creation_time: float = time.time()
    gpu_device_id: int = None

    @validator("priority")
    def check_priority(cls, v):
        if v < 1 or v > 5:
            raise ValueError("Priority must be between 1 and 5.")
        return v


class QueueItem:
    def __init__(self, job):
        self.job: Job = job

    def __repr__(self):
        return f"Queue item: {self.job}"

    def __lt__(self, other: Job):
        self_args = (-self.job.priority, other.job.creation_time)
        other_args = (-other.job.priority, other.job.creation_time)

        for self_arg, other_arg in zip(self_args, other_args):
            if self_arg > other_arg:
                return False
            elif self_arg < other_arg:
                return True

        return False


class ResourceQueue:
    def __init__(self, available_gpus_mem, available_threads, available_memory):
        self.gpu_devices_mem_max = available_gpus_mem.copy()
        self.gpu_devices_mem_available = available_gpus_mem.copy()
        self.num_gpus = len(self.gpu_devices_mem_available)
        self.threads_available = available_threads
        self.memory_available = available_memory
        self.threads_max = available_threads
        self.memory_max = available_memory
        self.job_queue: list[QueueItem] = []
        self.active_jobs = {}

    def add_job(
        self, job_id, priority, required_gpu_mem, required_threads, required_memory
    ):
        job = Job(
            ID=job_id,
            priority=priority,
            required_gpu_mem=required_gpu_mem,
            required_threads=required_threads,
            required_memory=required_memory,
        )
        if (
            job.required_gpu_mem > max(self.gpu_devices_mem_max)
            or job.required_threads > self.threads_max
            or job.required_memory > self.memory_max
        ):
            raise ValueError("Job requirements exceed available resources.")
        heapq.heappush(self.job_queue, QueueItem(job))
        self.process_queue()

    def _can_start(self, job):
        # TODO Maybe this check will make non-gpu requiring jobs wait for gpu?
        gpu_device_id = self.get_available_gpu_device(job.required_gpu_mem)
        return (
            gpu_device_id is not None
            and self.threads_available >= job.required_threads
            and self.memory_available >= job.required_memory
        )

    def _start(self, job):
        device_id = self.get_available_gpu_device(job.required_gpu_mem)
        self.gpu_devices_mem_available[device_id] -= job.required_gpu_mem
        self.threads_available -= job.required_threads
        self.memory_available -= job.required_memory
        job.gpu_device_id = device_id

    def _end(self, job):
        self.gpu_devices_mem_available[job.gpu_device_id] += job.required_gpu_mem
        self.threads_available += job.required_threads
        self.memory_available += job.required_memory

    def process_queue(self):
        while self.job_queue:
            job = self.job_queue[0].job

            if self._can_start(job):
                heapq.heappop(self.job_queue)
                self._start(job)
                self.active_jobs[job.ID] = job
            else:
                break

    def get_available_gpu_device(self, required_gpu_mem):
        for idx, available_mem in enumerate(self.gpu_devices_mem_available):
            if available_mem >= required_gpu_mem:
                return idx
        return None

    def end_job(self, job_id):
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            self._end(job)
            del self.active_jobs[job_id]
        else:
            self.remove_job_from_queue(job_id)

        self.process_queue()

    def is_job_active(self, job_id):
        if job_id in self.active_jobs:
            gpu_device_id = self.active_jobs[job_id].gpu_device_id
            return True, gpu_device_id
        else:
            return False, None

    def remove_job_from_queue(self, job_id):
        for index, jobq in enumerate(self.job_queue):
            if jobq.job.ID == job_id:
                self.job_queue.pop(index)
                heapq.heapify(self.job_queue)
                return True
        raise ValueError("Job not found in queue.")

    def get_resource_info(self):
        return {
            "gpu_devices_mem_available": [
                x - y
                for x, y in zip(
                    self.gpu_devices_mem_max, self.gpu_devices_mem_available
                )
            ],
            "gpu_devices_mem_max": self.gpu_devices_mem_max,
            "threads_available": self.threads_max - self.threads_available,
            "threads_max": self.threads_max,
            "memory_available": self.memory_max - self.memory_available,
            "memory_max": self.memory_max,
        }

    def get_queued_priorities(self):
        return [job[0] * -1 for job in self.job_queue]

    def get_load(self):
        sum_gpu_mem = (
            sum(self.gpu_devices_mem_max)
            if isinstance(self.gpu_devices_mem_max, list)
            else self.gpu_devices_mem_max
        )
        tot_required_gpu_mem = sum(
            x.required_gpu_mem for x in list(self.active_jobs.values()) + self.job_queue
        )
        tot_required_mem = sum(
            x.required_memory for x in list(self.active_jobs.values()) + self.job_queue
        )
        tot_required_threads = sum(
            x.required_threads for x in list(self.active_jobs.values()) + self.job_queue
        )

        load = max(
            tot_required_gpu_mem / sum_gpu_mem,
            tot_required_mem / self.memory_max,
            tot_required_threads / self.threads_max,
        )

        return load


templates = Jinja2Templates(
    directory=os.path.dirname(__file__) + "/resources/templates"
)


class RHManager(FastAPI):
    def __init__(self):
        super().__init__(
            docs_url="/manager/docs", openapi_url="/manager/api/openapi.json"
        )
        self.nodes = {}
        self.other_addrs = self._get_other_hosts()
        self.host_addr = self._get_own_host()

        self.queue = ResourceQueue(
            available_gpus_mem=[int(x) for x in os.environ["RH_GPU_MEM"].split(",")],
            available_threads=int(os.environ["RH_NUM_THREADS"]),
            available_memory=int(os.environ["RH_MEMORY"]),
        )
        self.setup_routes()

    def _get_own_host(self):
        return os.environ.get("RH_NAME", socket.gethostname() + ":9050")

    def _get_other_hosts(self):
        if not os.environ.get("RH_OTHER_ADDRESSES"):
            return []
        return os.environ.get("RH_OTHER_ADDRESSES").split(",")

    def has_node(self, node_name):
        return node_name in self.nodes.keys()

    ## Called by NodeRunner
    def get_addr_to_run_node(self, node_name):
        # return node_name

        if node_name in self.nodes.keys():
            lowest_load = self.queue.get_load()
            addr_with_lowest_load = "localhost:8000"
        else:
            lowest_load = None
            addr_with_lowest_load = None

        # query other hosts for available gpu
        for addr in self.other_addrs:
            url = f"http://{addr}/manager/dispatcher/has_node/{node_name}"
            response = requests.get(url)
            response.raise_for_status()
            has_node = response.json()
            assert isinstance(has_node, bool)
            if has_node:
                url = f"http://{addr}/manager/get_load"
                response = requests.get(url)
                response.raise_for_status()
                node_load = response.json()
                if lowest_load == None or node_load < lowest_load:
                    lowest_load = node_load
                    addr_with_lowest_load = addr

        if addr_with_lowest_load is not None:
            return addr_with_lowest_load
        else:
            raise Exception("No servers were found with the node")

    def setup_routes(self):
        @self.post("/manager/register_node")
        def _register_node(node: NodeMetaData):
            self.nodes[node.name] = node.dict()
            return "ok"

        @self.get("/manager/dispatcher/has_node/{node_name}")
        def _has_node(node_name):
            return self.has_node(node_name)

        @self.get("/manager/dispatcher/get_host/{node_name}")
        def _get_host_to_run_node(node_name):
            return self.get_addr_to_run_node(node_name)

        @self.post("/manager/add_job")
        async def add_job(job_request: QueueRequest):
            try:
                self.queue.add_job(
                    job_request.job_id,
                    job_request.priority,
                    job_request.required_gpu_mem,
                    job_request.required_threads,
                    job_request.required_memory,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            return {"message": "Job added successfully"}

        @self.post("/manager/end_job/{job_id}")
        async def end_job(job_id: str):
            # try:
            self.queue.end_job(job_id)
            # except ValueError as e:
            # raise HTTPException(status_code=400, detail=str(e))
            return {"message": "Job ended successfully"}

        @self.get("/manager/is_job_active/{job_id}")
        async def is_job_active(job_id: str):
            is_active, gpu_device_id = self.queue.is_job_active(job_id)
            return {"is_active": is_active, "gpu_device_id": gpu_device_id}

        @self.get("/manager/get_active_jobs")
        async def get_active_jobs():
            return [x.job.dict() for x in self.queue.active_jobs.values()]

        @self.get("/manager/get_queued_jobs")
        async def get_queued_jobs():
            return [x.job.dict() for x in self.queue.job_queue]

        @self.get("/manager/get_load")
        async def get_load():
            return self.queue.get_load()

        @self.get("/manager/get_resource_info")
        async def get_resource_info():
            return self.queue.get_resource_info()

        @self.get("/manager/ping")
        async def ping():
            return True

        @self.get("/manager/host_name")
        async def host_name():
            return self.host_addr.split(":")[0]

        @self.get("/")
        async def redirect_to_manager(request: Request):
            return RedirectResponse(url="/manager")

        @self.get("/manager")
        async def resource_queue(request: Request):
            active_jobs = [x.dict() for x in self.queue.active_jobs.values()]
            queued_jobs = [x.job.dict() for x in self.queue.job_queue]
            for job in active_jobs:
                splits = job["ID"].split("_")
                job["href"] = "/" + "_".join(splits[:-1]) + "/jobs/" + splits[-1]
            for job in queued_jobs:
                splits = job["ID"].split("_")
                job["href"] = "/" + "_".join(splits[:-1]) + "/jobs/" + splits[-1]

            available_resources = self.queue.get_resource_info()

            host_name = self.host_addr.split(":")[0]
            other_managers = [
                {"host": addr.split(":")[0], "port": addr.split(":")[1]}
                for addr in self.other_addrs
            ]
            gpu_info = []
            for i, (gpu_available, gpu_max) in enumerate(
                zip(
                    available_resources["gpu_devices_mem_available"],
                    available_resources["gpu_devices_mem_max"],
                )
            ):
                gpu_info.append(
                    {"id": i, "mem_available": gpu_available, "mem_max": gpu_max}
                )
            nodes = self.nodes.values()
            return templates.TemplateResponse(
                "resource_queue.html",
                {
                    "host_name": host_name,
                    "linked_servers": other_managers,
                    "request": request,
                    "active_jobs": active_jobs,
                    "queued_jobs": queued_jobs,
                    "gpus": gpu_info,
                    "threads_max": available_resources["threads_max"],
                    "threads_available": available_resources["threads_available"],
                    "memory_max": available_resources["memory_max"],
                    "memory_available": available_resources["memory_available"],
                    "nodes": nodes,
                    "rhnode_version": __version__,
                    "rhnode_mode": os.environ.get("RH_MODE", ""),
                },
            )


app = RHManager()
