import heapq
import fastapi
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
import uuid
import os
from pydantic import BaseModel
import time
import socket
from fastapi import FastAPI, HTTPException
from fastapi.templating import Jinja2Templates
from rhnode.utils import JobRequest, Node

class ResourceQueue:
    def __init__(self, available_gpus_mem, available_cores, available_memory):
        self.gpu_devices_mem_max = available_gpus_mem.copy()
        self.gpu_devices_mem_available = available_gpus_mem.copy()
        self.num_gpus = len(self.gpu_devices_mem_available)
        self.cores_available = available_cores
        self.memory_available = available_memory
        self.cores_max = available_cores
        self.memory_max = available_memory
        self.job_queue = []
        self.active_jobs = {}

    def add_job(self, job_id, priority, required_gpu_mem, required_cores, required_memory):
        if (priority < 1 or priority > 5):
            raise ValueError("Priority must be between 1 and 5.")
        
        if (required_gpu_mem > max(self.gpu_devices_mem_max) or
            required_cores > self.cores_max or
            required_memory > self.memory_max):
            raise ValueError("Job requirements exceed available resources.")

        heapq.heappush(self.job_queue, (-priority, job_id, required_gpu_mem, required_cores, required_memory))
        self.process_queue()

    def process_queue(self):
        while self.job_queue:
            _, job_id, required_gpu_mem, required_cores, required_memory = self.job_queue[0]

            gpu_device_id = self.get_available_gpu_device(required_gpu_mem)
            if (gpu_device_id is not None and
                self.cores_available >= required_cores and
                self.memory_available >= required_memory):

                heapq.heappop(self.job_queue)

                self.gpu_devices_mem_available[gpu_device_id] -= required_gpu_mem
                self.cores_available -= required_cores
                self.memory_available -= required_memory

                self.active_jobs[job_id] = (gpu_device_id, required_gpu_mem, required_cores, required_memory)
            else:
                break

    def get_available_gpu_device(self, required_gpu_mem):
        for idx, available_mem in enumerate(self.gpu_devices_mem_available):
            if available_mem >= required_gpu_mem:
                return idx
        return None

    def end_job(self, job_id):
        if job_id in self.active_jobs:

            gpu_device_id, required_gpu_mem, required_cores, required_memory = self.active_jobs[job_id]

            self.gpu_devices_mem_available[gpu_device_id] += required_gpu_mem
            self.cores_available += required_cores
            self.memory_available += required_memory

            del self.active_jobs[job_id]

        
        else:
            self.remove_job_from_queue(job_id)

        self.process_queue()

    def is_job_active(self, job_id):
        if job_id in self.active_jobs:
            gpu_device_id = self.active_jobs[job_id][0]
            return True, gpu_device_id
        else:
            return False, None
        

    def remove_job_from_queue(self, job_id):
        for index, job in enumerate(self.job_queue):
            if job[1] == job_id:
                self.job_queue.pop(index)
                heapq.heapify(self.job_queue)
                return True
        raise ValueError("Job not found in queue.")
    

    def get_resource_info(self):
        return {
            'gpu_devices_mem_available': [x-y for x,y in zip(self.gpu_devices_mem_max,self.gpu_devices_mem_available)],
            'gpu_devices_mem_max': self.gpu_devices_mem_max,
            'cores_available': self.cores_max-self.cores_available,
            'cores_max': self.cores_max,
            'memory_available': self.memory_max-self.memory_available,
            'memory_max': self.memory_max,
        }

    def get_queued_priorities(self):
        return [job[0] * -1 for job in self.job_queue]
    
    def get_active_jobs_info(self):
        active_jobs_info = []
        for job_id, (gpu_device_id, required_gpu_mem, required_cores, required_memory) in self.active_jobs.items():
            active_jobs_info.append({
                'gpu_device_id': gpu_device_id,
                'required_gpu_mem': required_gpu_mem,
                'required_cores': required_cores,
                'required_memory': required_memory,
                'job_id': job_id
            })
        return active_jobs_info

templates = Jinja2Templates(directory=os.path.dirname(__file__)+"/resources/templates")

class RHServer(FastAPI):
    def __init__(self):
        super().__init__(docs_url="/manager/docs",openapi_url="/manager/api/openapi.json")
        self.nodes = {}
        self.other_addrs = self._get_other_hosts()
        self.host_addr = self._get_own_host()
        self.queue = ResourceQueue(
            available_gpus_mem = [6],
            available_cores = 8,
            available_memory = 16
        )
        self.setup_routes()

    def _get_own_host(self):
        return os.environ.get('RH_ADDRESS', socket.gethostname()+":9050")
    
    def _get_other_hosts(self):
        if not os.environ.get('RH_OTHER_ADDRESSES'):
            return []
        return os.environ.get('RH_OTHER_ADDRESSES').split(",")

    def has_node(self, node_name):
        return node_name in self.nodes.keys()

    def has_available_gpu(self):
        return self.cuda_queue.has_available_gpu()

    ## Called by other dispatchers
    def get_port(self, node_name):
        return self.nodes[node_name]["port"]

    ## Called by NodeRunner
    def get_addr_to_run_node(self, node_name):
        #return node_name
        
        if not self.node_requires_gpu[node_name]:
            return node_name+":8000"
        if self.has_available_gpu():
            return node_name+":8000"
        
        #query other hosts for available gpu
        for addr in self.other_addrs:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            url = f"http://{addr}/dispatcher/has_node/{node_name}"
            response = requests.request("GET", url, headers=headers)
            response.raise_for_status()
            has_node = response.json()
            if not has_node:
                continue
            url = f"http://localhost:8000/dispatcher/has_available_gpu"
            response = requests.request("GET", url, headers=headers)
            response.raise_for_status()
            has_available_gpu = response.json()
            if has_available_gpu:
                return host

        return "localhost"


    def setup_routes(self):

        @self.post("/manager/register_node")
        def _register_node(node:Node):
            self.nodes[node.name] = node.dict()
            return "ok"

        @self.get("/manager/dispatcher/has_node/{node_name}")
        def _has_node(node_name):
            return self.has_node(node_name)
        
        @self.get("/manager/dispatcher/has_available_gpu")
        def _has_available_gpu():
            return self.has_available_gpu()

        @self.get("/manager/dispatcher/get_host/{node_name}")
        def _get_host_to_run_node(node_name):
            return self.get_addr_to_run_node(node_name)
        
        @self.post("/manager/add_job")
        async def add_job(job_request: JobRequest):
            try:
                self.queue.add_job(job_request.job_id, job_request.priority, job_request.required_gpu_mem, job_request.required_cores, job_request.required_memory)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            return {"message": "Job added successfully"}
    
        @self.post("/manager/end_job/{job_id}")
        async def end_job(job_id: str):
            #try:
            self.queue.end_job(job_id)
            #except ValueError as e:
            #raise HTTPException(status_code=400, detail=str(e))
            return {"message": "Job ended successfully"}

        @self.get("/manager/is_job_active/{job_id}")
        async def is_job_active(job_id: str):
            is_active, gpu_device_id = self.queue.is_job_active(job_id)
            return {"is_active": is_active, "gpu_device_id": gpu_device_id}

        @self.get("/manager/get_active_jobs")
        async def get_active_jobs():
            return self.queue.get_active_jobs_info()

        @self.get("/manager/get_queued_jobs")
        async def get_queued_jobs():
            return {"queued_jobs": [{"priority": job[0] * -1, "job_id": job[1], "required_gpu_mem": job[2], "required_cores": job[3], "required_memory": job[4]} for job in self.queue.job_queue]}

        @self.get("/manager/get_resource_info")
        async def get_resource_info():
            return self.queue.get_resource_info()


        @self.get("/")
        async def redirect_to_manager(request: Request):
            return RedirectResponse(url="/manager")

        @self.get("/manager")
        async def resource_queue(request: Request):
            active_jobs = self.queue.get_active_jobs_info()
            queued_jobs = [{"priority": job[0] * -1, "job_id": job[1], "required_gpu_mem": job[2], "required_cores": job[3], "required_memory": job[4]} for job in self.queue.job_queue]
            available_resources = self.queue.get_resource_info()
            
            for active_job in active_jobs:
                splits = active_job["job_id"].split("_")
                active_job["href"] = "/" + "_".join(splits[:-1]) + "/show/" + splits[-1]
                
            for queued_job in queued_jobs:
                splits = queued_job["job_id"].split("_")
                queued_job["href"] = "/" + "_".join(splits[:-1]) + "/show/" + splits[-1]

            gpu_info = []
            for i, (gpu_available,gpu_max) in enumerate(zip(available_resources["gpu_devices_mem_available"], available_resources["gpu_devices_mem_max"])):
                gpu_info.append(
                    {
                        "id": i,
                        "mem_available": gpu_available,
                        "mem_max": gpu_max
                    }
                )
            nodes = self.nodes.values()
            return templates.TemplateResponse("resource_queue.html", {
                "request": request,
                "active_jobs": active_jobs,
                "queued_jobs": queued_jobs,
                "gpus": gpu_info,
                "cores_max": available_resources["cores_max"],
                "cores_available": available_resources['cores_available'],
                "memory_max": available_resources["memory_max"],
                "memory_available": available_resources['memory_available'],
                "nodes": nodes
            })
        


app = RHServer()