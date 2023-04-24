
from fastapi import FastAPI, Request
import requests
from fastapi.responses import HTMLResponse
from jinja2 import Environment, PackageLoader
import uuid
import os

env = Environment(loader=PackageLoader(__name__, os.path.dirname(__file__)+"/resources/templates"))

class Queue:
    def __init__(self):
        self.queue = []
    
    def push(self, item):
        assert item not in self.queue
        self.queue.append(item)

    def pop(self):
        if len(self.queue) == 0:
            raise IndexError("Queue is empty")
        return self.queue.pop(0)
    
    def get_place_in_queue(self, item):
        for i, qitem in enumerate(self.queue):
            if qitem == item:
                return i
            
        raise Exception("Item not found")

    def remove(self, item):
        for i, qitem in enumerate(self.queue):
            if qitem == item:
                self.queue.pop(i)
                return True
        raise Exception("Item not found")



class CudaQueue:
    def __init__(self):
        self.queue = Queue()
        self.available_gpus = [0, 1, 2, 3]
        self.gpu_to_job = {i:None for i in self.available_gpus}
    
    def _get_available_gpu(self):
        if not os.environ.get('CUDA_DEVICES'):
            return None

    def _maybe_activate(self):
        if len(self.queue.queue) == 0:
            return
        for gpu_id, job_id in self.gpu_to_job.items():
            if job_id == None:
                item = self.queue.pop()
                self.gpu_to_job[gpu_id] = item
                return

    def queue_item(self):
        #create uuid
        item = str(uuid.uuid4())
        self.queue.push(item)
        self._maybe_activate()
        return item

    def dequeue_item(self, item):
        for gpu_id, job_id in self.gpu_to_job.items():
            if job_id == item:
                self.gpu_to_job[gpu_id] = None
                self._maybe_activate()
                return
        
        if self.queue.remove(item):
            return
        else:
            raise Exception("Item not found")
    
    def clear_queue(self):
        self.queue = Queue()
        self.gpu_to_job = {i:None for i in self.available_gpus}

    def get_active(self):
        return self.gpu_to_job.copy()
    
    def get_queued(self):
        return self.queue.queue.copy()

    def get_status(self, item):
        for gpu_id, job_id in self.gpu_to_job.items():
            if job_id == item:
                return gpu_id
            
        assert item in self.queue.queue

        return None
    
    def has_available_gpu(self):
        return  any([ID == None for ID in self.gpu_to_job.values()])




class RHServer(FastAPI):
    def __init__(self,other_hosts=[]):
        super().__init__()
        self.node_names = []
        self.node_requires_gpu = {}
        self.other_hosts = other_hosts
        self.cuda_queue = CudaQueue()
        self.setup_routes()

    def has_node(self, node_name):
        return node_name in self.node_names

    def has_available_gpu(self):
        return self.cuda_queue.has_available_gpu()

    def get_host_to_run_node(self, node_name,):
        return node_name
        
        if not self.node_requires_gpu[node_name]:
            return node_name+":8000"
        if self.has_available_gpu():
            return node_name+":8000"
        
        #query other hosts for available gpu
        for host in self.other_hosts:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            url = f"http://localhost:8000/dispatcher/has_node/{node_name}"
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

    def get_queue_status(self, job_id):
        return self.cuda_queue.get_status(job_id)
    
    def queue_cuda_job(self):
        return self.cuda_queue.queue_item()
    
    def release_cuda_job(self,job_id):
        return self.cuda_queue.dequeue_item(job_id)


    def clear_queue(self):
        self.cuda_queue.clear_queue()

    def setup_routes(self):
        @self.get("/dispatcher/has_node/{node_name}")
        def _has_node(node_name):
            return self.has_node(node_name)
        
        @self.get("/dispatcher/has_available_gpu")
        def _has_available_gpu():
            return self.has_available_gpu()

        @self.get("/dispatcher/get_host/{node_name}")
        def _get_host_to_run_node(node_name):
            return self.get_host_to_run_node(node_name)
        
        @self.get("/queue/add")
        def _queue_cuda_job():
            return self.queue_cuda_job()
        @self.get("/queue/status/{job_id}")
        def _get_queue_status(job_id):
            return self.get_queue_status(job_id)
        
        @self.get("/queue/remove/{job_id}")
        def _release_cuda_job(job_id):
            return self.release_cuda_job(job_id)

        @self.get("/queue/clear")
        def _clear_queue():
            return self.clear_queue()

        @self.get("/", response_class=HTMLResponse)
        async def show_task_status(request: Request):
            # Load the template from the package
            template = env.get_template('queue_status.html')
            queued = self.cuda_queue.get_queued()
            active = self.cuda_queue.get_active()
            formats = []
            for gpu_id, ID in active.items():
                formats.append(
                    {
                        "id": ID,
                        "gpu_id": gpu_id,
                    }
                )
            
            # Render the template with the tasks
            html_content = template.render(active=formats,queued=queued)

            # Return the rendered webpage
            return html_content

app = RHServer()