See the [contributing section](/docs/contributing.md) if you wish to make changes to RHNode. 
See [this guide](docs/docker_and_ssh.md) if you are experiencing problems with ssh after docker installation. 
See [rh-library](https://github.com/CAAI/rh-library) for nodes in production. 

# Getting Started with RHNode Library

RHNode is a library for deploying deep learning models by creating REST endpoints. In this guide, you will learn how to use the RHNode library to define your custom node, run, and test it using the NodeRunner, containerize the node using docker and deploy the model. See the `example` folder for the code accompanying this tutorial.

## 1 Install RHNode

Install the RHNode library using `pip`from the GitHub repository:

```cmd
pip install git+https://github.com/CAAI/rh-node.git
```

## 2 Defining an RHNode

To define an RHNode, follow these steps:

1. In a new file, import the specific classes/functions for your machine learning model.
2. Define input and output specifications using Pydantic BaseModel.
3. Create a custom class for your node that inherits from `RHNode`.
4. Define resource requirements and other configurations.
5. Override the `process` function with your machine learning model's inference logic.


Here's an example of a simple custom node called `AddNode`.

`add.py`:

```python
from rhnode import RHNode
from pydantic import BaseModel, FilePath
import nibabel as nib
import time


class InputsAdd(BaseModel):
    scalar: int
    in_file: FilePath


class OutputsAdd(BaseModel):
    out_file: FilePath
    out_message: str


class AddNode(RHNode):
    input_spec = InputsAdd
    output_spec = OutputsAdd
    name = "add"
    required_gb_gpu_memory = 1
    required_num_threads = 1
    required_gb_memory = 1

    def process(inputs, job):
        img = nib.load(inputs.in_file)
        arr = img.get_fdata() + inputs.scalar
        img = nib.Nifti1Image(arr, img.affine, img.header)
        outpath = job.directory / "added.nii.gz"
        img.to_filename(outpath)
        time.sleep(3)
        return OutputsAdd(out_file=outpath, out_message="this worked")


app = AddNode()
```

The following fields should be defined:
- `input_spec`: The inputs recieved by the node. Note that objects which are not JSON serializable (numpy arrays, nifti files, etc.) should be of type `FilePath`. RHNode will handle the transfer of these files and provide a path where the file can be found. `input_spec` must inherit from `pydantic.BaseModel`

- `output_spec`: The outputs returned by the node. Objects that are not JSON serializable should be saved to disk inside the `process` function. Then use the paths to these saved files in the output_spec. NOTE! It is important that all such saved files are saved in a subdirectory of job.directory. This is to ensure proper cleanup after the node has finished. `output_spec` must inherit from `pydantic.BaseModel`

- `name`: A unique name used to identify the node.
- `required_gb_gpu_memory`: 
- `required_num_threads`:
- `required_gb_memory`:


The `process` function accepts two arguments: an instance of `input_spec` and a `job` metadata instance. 

The job metadata contains two important attributes; `job.device` and `job.directory`. If `required_gb_gpu_memory>0`, then a CUDA device will be reserved and given to the process via `job.device` (an integer). All cuda devices are visible to the `process` function, so it is important that all GPU operations are performed only on the designated `job.device` as not to interfere with the memory of other jobs. The `job.directory` attribute specifies a folder in which all file outputs of the process function are expected to be saved. 

Also, if your `process` function makes calls to other nodes (see later section), the same `job` instance should be passed on to these. Among other things, this is to ensure that such child jobs will have the same job priority as the parent job. 

## 3 Starting the server
Change directory to where `add.py` lies and run the following command:

```cmd
uvicorn add:app --port 8010
```
Alternatively, you can add the following to your launch.json (vscode), which allows you to debug the server node while it runs:

```json
{
    "name": "run_add_node",
    "type": "python",
    "request": "launch",
    "module":"uvicorn",
    "console": "integratedTerminal",
    "args": ["example.add_node_project.add:app","--port","8010"],
}
```
If you get an `"[Errno 98] ... address already in use"` error, try with a different port. 

Note that the node will print `Could not register with manager`, which is expected at this stage.

The rhnode server now runs, and is accessible from the webbrowser on http://localhost:8010/add.

## 4 Testing the Node
To test the node, you can create a separate script, `test_addnode.py`, that uses the `RHJob` class to send inputs and receive outputs from your custom node. Follow these steps:

1. Import the required classes and functions.
2. Define the inputs to the node you wish to run.
3. Define the job parameters (priority, whether to check cache) in `RHJob`.
4. Start the node.
5. Either wait for the node to finish or stop the node.

Here's an example of how to invoke the `AddNode`:

```python
from rhnode import RHJob

# NOTE: manager_adress and node_address are mutually exclusive.

data = {
    "scalar": 3,
    "in_file": "/homes/hinge/Projects/rh-node/tests/data/mr.nii.gz",
}

node = RHJob(
    node_name="add",
    inputs=data,
    node_address="localhost:8010",
    output_directory=".",
    resources_included=True,
    included_cuda_device=0,  # if applicable
    priority=3,
    check_cache=False,
)
# Wait for the node to finish
node.start()

output = node.wait_for_finish()

# Alternatively to interrupt the job:
# node.stop()
```
A few things to note in this example:
- By default when running a node, the result is saved in a cache. If the node is invoked again with the same inputs, then the cached result will be returned immediately. `check_cache=False` turns off this functionality, which might be benifical for debugging purposes. 
- Usually, the host and port of the node should not be specified explicitly. In production, the NodeRunner will ask a "manager" node where to find the add-node. 
- `resources_included=True` is likewise included for debugging purposes. By default,  any node run will ask a manager node to allocate resources for it via a queue. However, there is no manager node during debugging. `resources_included=True` lets the node know that resources have already been allocated. We then specify the GPU device id manually by `included_cuda_device=0`. Again this is just for debugging purposes


That's it! You've learned how to define and use your custom node with the RHNode library.


## 5 Containerize the node with Docker

The next step is to dockerize your node. First install docker via:

1. Install Docker. Follow the steps on https://docs.docker.com/engine/install/ubuntu/ 
2. Install nvidia-docker dependencies. Follow the steps on https://www.howtogeek.com/devops/how-to-use-an-nvidia-gpu-with-docker-containers/
3. If new to docker, this 10 min video is a very good introduction: https://www.youtube.com/watch?v=gAkwW2tuIqE&t=361s 


Step 1: Create a file in the project root named `Dockerfile`. Here is a finished Dockerfile for the `add` node:


```Dockerfile
#System
FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime
# FROM python:3.8 #If GPU is not necessary
RUN apt-get update -y
RUN apt-get install git -y

#General requirements
ADD https://api.github.com/repos/CAAI/rh-node/git/refs/heads/main version_rhnode.json
RUN pip install git+https://github.com/CAAI/rh-node.git

#Unique to project requirements
COPY add.py /app/add.py
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
WORKDIR /app

## Command to start the server
CMD ["uvicorn", "add:app", "--host", "0.0.0.0", "--port", "8000"]
```
A few things to note:
- For the line starting with `CMD`: The port should be kept at `8000`. Only the `"add:app"` part should be changed. 

- The Docker container will later become public, so ensure that no patient data is copied to the container. When the app was previously ran via `uvicorn` (see part 3), three folders are created in the working directory `.outputs`, `.cache`, and `.inputs`. Make sure that these are not copied to the Docker container, as they may contain patient data from previous jobs.

- If your model downloads weights from zenodo or similar, ensure that these are manually downloaded as a step in the Dockerfile (see RHNode hdbet node as example). Otherwise, each time the container is run, the model weights will be redownloaded.

- If your model installs from a github repo and you wish to ensure the newest version is used (rather than caching from the last build) replace the `RUN git clone https://github.com/$USER/$REPO` line with: 
`ADD https://api.github.com/repos/$USER/$REPO/git/refs/heads/$BRANCH version.json` and `RUN git clone -b $BRANCH https://github.com/$USER/$REPO` or similar for `RUN pip install` as above.

- We have created a `requirements.txt` which specifies `nibabel` as the only dependency. 

Step 2: Build the image via a docker compose. Create a docker-compose.yaml file in the same directory as the Dockerfile:


```yaml

version: "1" #Arbitrary
services:

  add: #CHANGE to Same name as node.name
    image: rhnode/add:latest #CHANGE also
    build: .
    ports:
      - "8010:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

```

In the same directory as the `docker-compose.yaml` file, run:

`docker compose up --build`

The initial build may take a few minutes but subsequent builds should be quick. 

If everything works, the webserver should be accessible at http://localhost:8010/add like previously. You can test node again with the test script to ensure that everything works.

Once production ready, you can push the image to Dockerhub. Note that you will have to login. 

`docker compose build --push`

The image will be saved according to the image attribute in the docker-compose file (`rhnode/add:latest`). If your node is general purpose, the image can be saved to the rhnode Dockerhub account. Otherwise, feel free to create an account on Dockerhub and push your node to that account. 

## 6 Internode dependence

If your node uses NodeRunner to run other nodes as a step in the process function, then those nodes should also be running during development. Here is an example node that depends on the previously defined add node. 

```python
from rhnode import RHNode, RHJob
from pydantic import BaseModel, FilePath
import nibabel as nib


class MyInputs(BaseModel):
    multiplier: int
    in_file: FilePath


class MyOutputs(BaseModel):
    message: str
    img1: FilePath
    img2: FilePath


class MyDependentNode(RHNode):
    input_spec = MyInputs
    output_spec = MyOutputs
    name = "mydependent"

    required_gb_gpu_memory = 1
    required_num_threads = 1
    required_gb_memory = 1

    def process(inputs, job):
        add_inputs = {"scalar": 1, "in_file": inputs.in_file}
        add_1_node = RHJob.from_parent_job("add", add_inputs, job)

        add_inputs = {"scalar": 1, "in_file": inputs.in_file}
        add_2_node = RHJob.from_parent_job("add", add_inputs, job)

        # Start nodes in parallel
        add_1_node.start()
        add_2_node.start()

        # Wait for node 1 to finish and multiply it by the multiplier constant
        outputs_1 = add_1_node.wait_for_finish()
        img = nib.load(outputs_1["out_file"])
        arr = img.get_fdata() * inputs.multiplier
        img = nib.Nifti1Image(arr, img.affine, img.header)
        outpath = job.directory / "img1.nii.gz"
        img.to_filename(outpath)

        # Wait for node 2 to finish and leave it as is
        outputs_2 = add_2_node.wait_for_finish()

        return MyOutputs(
            message="Hello World", img1=outpath, img2=outputs_2["out_file"]
        )


app = MyDependentNode()
```
Create a `Dockerfile` for MyDependentNode similar to before.
Now create a `docker-compose.yaml` in the same folder as the `Dockerfile`:


```yaml
version: "1"
services:
  reverse-proxy:
    # The official v2 Traefik docker image
    image: traefik:v2.9
    # Enables the web UI and tells Traefik to listen to docker
    command: --api.insecure=true --providers.docker
    ports:
      # The HTTP port
      - "9050:80"
      # The Web UI (enabled by --api.insecure=true)
      - "9051:8080"
    volumes:
      # So that Traefik can listen to the Docker events
      - /var/run/docker.sock:/var/run/docker.sock

  #Queue Node
  manager:
    image: rhnode/manager:latest

    expose:
    - "8000"

    labels:
      - "traefik.http.routers.manager.rule=PathPrefix(`/manager`) || Path(`/`)"

    environment: 
      RH_NAME: "tower" #CHANGE: peyo to the name of your host (e.g. titan6, myubuntu, caai1)
      RH_MEMORY: 16 #CHANGE:  GB RAM on machine
      RH_GPU_MEM: "8" #CHANGE: GB GPU on machine. If multiple GPUs, make a list like: "8,8,12"
      RH_NUM_THREADS: 4 #CHANGE: The number of threads on your machine

  ## Test node
  add: # CHANGE: to the name of the image which mydependent node depends on
    image: rhnode/add:latest #CHANGE: to the image of whichever node mydependent node depends on

    expose:
      - "8000"
    labels:
      - "traefik.http.routers.add.rule=PathPrefix(`/add`)" #CHANGE: to "traefik.http.routers.[NODE_NAME].rule=PathPrefix(`/[NODE_NAME]`)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  ## Test node
  mydependent: #CHANGE: to the name of your node
    image: rhnode/mydependent:latest # CHANGE: to the image name of your node

    build: .

    expose:
      - "8000"
    labels:
      - "traefik.http.routers.mydependent.rule=PathPrefix(`/mydependent`)" #CHANGE: to "traefik.http.routers.[NODE_NAME].rule=PathPrefix(`/[NODE_NAME]`)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Lines which you might wish to change are marked with `"#CHANGE:..."`.

A few new things are introduced here:

- All nodes now run at port `9050`
The `manager` node keeps track of jobs running across different nodes on the host. The manager can be accessed at http://localhost:9050/manager.
- The `reverse-proxy` container routes urls to specific container nodes. For instance all urls starting with, `/add`, will be routed to the `add`-node container. 
- Note that there is no `build` attribute of the `add`-, `manager`-, and `reverse-proxy`-node. These containers will be pulled from Dockerhub. 

Start the server (make sure you are in the folder with the correct `docker-compose.yaml`):

```docker compose up --build```

Test the dependent node with a script similar to that of part 4:

```python
from rhnode import RHJob

data = {"multiplier": 3, "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"}

job = RHJob(
    node_name="dependent",
    inputs=data,
    output_directory=".",
    priority=3,
    check_cache=False,
)

job.start()
job.wait_for_finish()

```
Since we are now running a manager in our cluster, there is no need to manually assign resources to the job. 

## 7 Production
Setup a cluster of rhnodes on a machine:
1. Install docker and nvidia-docker on the machine as outlined in part 5
2. Copy the `docker-compose.yaml` file from part 6 to the machine, and change relevant fields:
    - Add the nodes you wish to have running on the machine (make sure that they have been pushed to Dockerhub).
    - Delete the `build` attribute of each node. 
    - In the manager node, change env. variables `RH_NAME`, `RH_MEMORY`, `RH_GPU_MEM`, and `RH_NUM_THREADS`
    - In the manager node, define env. variable `RH_OTHER_ADDRESSES` with the adresses of other rhnode clusters. Example: RH_OTHER_ADDRESSES: `"peyo:9050,titan6:9050"`
3. Run `docker compose up -d` (`-d` detaches the process)

If you wish to stop the containers, run:
`docker compose down`

If you wish to update the containers from a newer version on Dockerhub, run:
`docker compose pull`

This can be done while the containers are running. To restart the containers do:
`docker compose up -d`
