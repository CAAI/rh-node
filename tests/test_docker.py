# Larger tests that requires multiple nodes running and interaction
# These tests are done on a running docker compose session

### HOW TO USE

## 1 in terminal, cd to tests
## 2 run "docker compose up --build"
## 3 open another terminal
## 4 run pytest
## (5 check terminal with docker images that nothing breaks)


## Make sure you have the file "tests/data/mr.nii.gz". This can be any nifti file.
NII_FILE = "tests/data/mr.nii.gz"

import pytest
from rhnode import RHJob
import requests
import os
import shutil
from rhnode.common import JobStatus, JobCancelledError, JobFailedError
import time

ADDRESS = "localhost:9050"
ENDPOINT = "http://" + ADDRESS
ENDPOINT_ADD = ENDPOINT + "/add"
ENDPOINT_MANAGER = ENDPOINT + "/manager"


def test_read_root_node():
    requests.get(ENDPOINT_ADD).raise_for_status()


def test_read_root_manager():
    requests.get(ENDPOINT).raise_for_status()
    requests.get(ENDPOINT_MANAGER).raise_for_status()


# test output
@pytest.mark.parametrize("param", [True, False])
def test_output(tmp_path, param):
    if param:
        output_directory = tmp_path / "output"
        expected_output_directory = output_directory
    else:
        output_directory = None
        expected_output_directory = "add"
        assert not os.path.exists(expected_output_directory)

    data = {"scalar": 3, "in_file": NII_FILE, "sleep_time": 0, "throw_error": False}

    node = RHJob(
        node_name="add",
        inputs=data,
        node_address=ADDRESS,
        check_cache=True,
        output_directory=output_directory,
        resources_included=True,
    )

    node.start()
    output = node.wait_for_finish()
    assert output["out_message"] == "this worked"
    assert os.path.exists(expected_output_directory)
    assert len(os.listdir(expected_output_directory)) == 1
    assert os.path.exists(os.path.join(expected_output_directory, "added1.nii.gz"))
    assert JobStatus(node._get_status()) == JobStatus.Finished
    shutil.rmtree(expected_output_directory)


# test output
@pytest.mark.parametrize("device", [0, 1])
def test_manual_device(tmp_path, device):
    data = {
        "scalar": 3,
        "in_file": NII_FILE,
        "sleep_time": 0,
        "throw_error": False,
        "check_device_allocated": 0,
    }

    node = RHJob(
        node_name="add",
        inputs=data,
        node_address=ADDRESS,
        check_cache=False,
        output_directory=tmp_path,
        resources_included=True,
        included_cuda_device=device,
    )

    node.start()
    if device == 0:
        node.wait_for_finish()
    else:
        with pytest.raises(JobFailedError):
            node.wait_for_finish()


def test_error_propagation(tmp_path):
    data = {"scalar": 3, "in_file": NII_FILE, "sleep_time": 0, "throw_error": True}

    node = RHJob(
        node_name="add",
        inputs=data,
        node_address=ADDRESS,
        check_cache=False,
        output_directory=tmp_path,
        resources_included=True,
    )

    node.start()
    with pytest.raises(JobFailedError):
        node.wait_for_finish()


def test_queue_and_cancel(tmp_path):
    data = {
        "scalar": 3,
        "in_file": NII_FILE,
        "sleep_time": 60,
    }

    jobs = []

    for i in range(3):
        job = RHJob(
            node_name="add",
            inputs=data,
            check_cache=False,
            output_directory=tmp_path / "output",
        )
        job.start()
        jobs.append(job)

    time.sleep(1)

    for i in range(2):
        assert JobStatus(jobs[i]._get_status()) == JobStatus.Running
    assert JobStatus(jobs[2]._get_status()) == JobStatus.Queued
    for i in range(2):
        jobs[i].stop()
        assert JobStatus(jobs[i]._get_status()) == JobStatus.Cancelled
    assert JobStatus(jobs[2]._get_status()) == JobStatus.Running
    jobs[2].stop()


def test_finish_and_caching(tmp_path):
    data = {"scalar": 3, "in_file": NII_FILE, "sleep_time": 5, "throw_error": False}

    node = RHJob(
        node_name="add",
        inputs=data,
        node_address=ADDRESS,
        check_cache=False,
        output_directory=tmp_path,
        resources_included=True,
    )

    start = time.time()
    node.start()
    output = node.wait_for_finish()
    end = time.time()
    diff = end - start
    print(diff)
    assert diff > 5

    node = RHJob(
        node_name="add",
        inputs=data,
        node_address=ADDRESS,
        check_cache=True,
        output_directory=tmp_path,
        resources_included=True,
    )
    start = time.time()
    node.start()
    output = node.wait_for_finish()
    end = time.time()
    assert end - start < 5


def test_dependent(tmp_path):
    data = {"multiplier": 3, "in_file": NII_FILE}
    output_directory = tmp_path / "output"
    job = RHJob(node_name="dependent", inputs=data, output_directory=output_directory)

    job.start()
    output = job.wait_for_finish()

    assert os.path.exists(output_directory)
    assert len(os.listdir(output_directory)) == 2
    assert os.path.exists(os.path.join(output_directory, "img1.nii.gz"))
    assert os.path.exists(os.path.join(output_directory, "added1.nii.gz"))
