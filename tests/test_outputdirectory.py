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
import os
import shutil
from pathlib import Path

""" OutputDirectory NODE """

def test_output_directory_no_file_return_1(tmp_path):
    data = {
        'in_file': NII_FILE, 
        'return_output_file': False
    }
    output_directory = 'outputdirectory'

    job = RHJob(node_name="outputdirectory", inputs=data, output_directory=output_directory)
    job.start()
    output = job.wait_for_finish()

    assert not os.path.exists(output_directory)
    assert output['out_file'] is None

def test_output_directory_no_file_return_2(tmp_path):
    data = {
        'in_file': NII_FILE, 
        'return_output_file': False
    }
    output_directory = 'outputdirectory'

    job = RHJob(node_name="outputdirectory", inputs=data)
    job.start()
    output = job.wait_for_finish()

    assert not os.path.exists(output_directory)
    assert output['out_file'] is None


def test_output_directory_file_return_1(tmp_path):
    data = {
        'in_file': NII_FILE, 
        'return_output_file': True
    }
    output_directory = tmp_path / 'custom_folder'
    output_directory.mkdir()

    job = RHJob(node_name="outputdirectory", inputs=data, output_directory=output_directory)
    job.start()
    output = job.wait_for_finish()

    assert os.path.exists(output_directory)
    assert os.path.exists(os.path.join(output_directory, "image.nii.gz"))
    assert output['out_file'] == (output_directory/"image.nii.gz")

def test_output_directory_file_return_2(tmp_path):
    data = {
        'in_file': NII_FILE, 
        'return_output_file': True
    }
    output_directory = 'outputdirectory' # Created by node

    job = RHJob(node_name="outputdirectory", inputs=data)
    job.start()
    output = job.wait_for_finish()

    assert os.path.exists(output_directory)
    assert os.path.exists(os.path.join(output_directory, "image.nii.gz"))
    assert str(output['out_file'].absolute()) == str((Path(output_directory) / "image.nii.gz").absolute())

    # Cleanup
    shutil.rmtree(output_directory, ignore_errors=True)

def test_output_directory_file_return_3(tmp_path):
    data = {
        'in_file': NII_FILE, 
        'return_output_file': True
    }

    # Add first a directory to trigger outputdirectory_1 to be created by node
    tmp_dir = Path('outputdirectory')
    tmp_dir.mkdir()
    output_directory = 'outputdirectory_1' # Created by node

    job = RHJob(node_name="outputdirectory", inputs=data)
    job.start()
    output = job.wait_for_finish()

    assert os.path.exists(tmp_dir)
    assert os.path.exists(output_directory)
    assert os.path.exists(os.path.join(output_directory, "image.nii.gz"))
    assert str(output['out_file'].absolute()) == str((Path(output_directory) / "image.nii.gz").absolute())

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)
    shutil.rmtree(output_directory, ignore_errors=True)