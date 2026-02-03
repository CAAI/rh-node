# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is RHNode

RHNode is a Python library for deploying deep learning models as REST endpoints. It handles job queuing, resource allocation (GPU/CPU/memory), file transfers, caching, and inter-node dependencies. Used at CAAI (Clinical AI) at Rigshospitalet, Copenhagen.

## Common Commands

### Running Tests
```bash
# Start the test cluster (in tests/ directory)
cd tests && docker compose up --build

# In another terminal, run all tests
pytest

# Run a specific test file
pytest test_docker.py

# Run a specific test
pytest test_docker.py::test_finish_and_caching
```

### Running a Node Locally (Development)
```bash
# Start a single node server
uvicorn add:app --port 8010

# Access at http://localhost:8010/add
```

### CLI Tool
```bash
# Run a job via CLI
rhjob <node_name> input_key=value input_file=/path/to/file.nii.gz

# Get help for a specific node
rhjob <node_name> -h
```

### Docker
```bash
# Build and run with docker compose
docker compose up --build

# Build and push to DockerHub
docker compose build --push
```

## Architecture

### Core Components

**RHNode** ([rhnode/rhnode.py](rhnode/rhnode.py)) - Base class for creating node servers. Subclass this to create a new node:
- Define `input_spec` and `output_spec` as Pydantic BaseModel classes
- Override the `process(inputs, job)` static method with inference logic
- Set resource requirements: `required_gb_gpu_memory`, `required_num_threads`, `required_gb_memory`

**RHJob** ([rhnode/rhjob.py](rhnode/rhjob.py)) - Client for submitting jobs to nodes. Handles file uploads, polling for completion, and downloading results.

**RHProcess** ([rhnode/rhprocess.py](rhnode/rhprocess.py)) - Server-side job execution. Manages job lifecycle: file uploads → queue → run process → cleanup.

**RHManager** ([nodes/manager/manager.py](nodes/manager/manager.py)) - Resource queue manager. Allocates GPU/CPU/memory across jobs using a priority queue. Multiple RHNode clusters can link together via `RH_OTHER_ADDRESSES`.

**Common types** ([rhnode/common.py](rhnode/common.py)) - Shared Pydantic models: `JobMetaData`, `JobStatus`, `QueueRequest`, etc.

### Data Flow

1. Client creates `RHJob` with inputs → POST to node creates `RHProcess`
2. File inputs uploaded one by one to `.inputs/<job_id>/`
3. Job enters resource queue via manager (unless `resources_included=True`)
4. When resources available, `process()` runs in subprocess with allocated `job.device`
5. Outputs saved to `.outputs/<job_id>/`, optionally cached to `.cache/`
6. Client downloads file outputs, job auto-deleted after 10 minutes

### Key Patterns

- **FilePath fields**: Input/output Pydantic models use `FilePath` for files that need to be transferred. Non-serializable data (numpy arrays, nifti images) must be saved to disk.
- **job.directory**: All output files must be saved within `job.directory` for proper cleanup.
- **job.device**: The allocated CUDA device ID. Only use this device for GPU operations.
- **Child jobs**: Use `RHJob.from_parent_job()` to spawn dependent jobs that inherit priority and resource settings.
- **Caching**: Results are cached by input hash. Use `check_cache=False` during development.

### Environment Variables

For the manager node:
- `RH_NAME`: Host identifier
- `RH_GPU_MEM`: GPU memory per device, comma-separated for multiple GPUs (e.g., "8,8,12")
- `RH_NUM_THREADS`: Available CPU threads
- `RH_MEMORY`: Available RAM in GB
- `RH_OTHER_ADDRESSES`: Comma-separated addresses of other managers (e.g., "titan6:9050,peyo:9050")

For nodes:
- `RH_EMAIL_ON_ERROR`: Email recipient for error notifications
- `RH_MODE`: Set to "dev" for development mode

## Versioning

Version format: `major.minor.patch`
- Development branches: `dev/v1.X.0`
- Alpha releases: `v1.X.0-a.N`
- When tagging docker images for rh-library, omit the hyphen: `hdbet-v1.1.0_rhnode1.2.0a.1`

## Test Data

Tests require a NIfTI file at `tests/data/mr.nii.gz`. This can be any valid nifti file.
