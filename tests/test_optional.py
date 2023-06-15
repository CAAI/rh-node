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

def test_optional_input_1(tmp_path):
    data = {
        'in_file': NII_FILE, 
        'return_output_file': False
    }
    optional = 'optional'

    job = RHJob(node_name="optional", inputs=data, output_directory=optional)
    job.start()
    output = job.wait_for_finish()

    assert not os.path.exists(optional)
    assert output['out_file'] is None

    # Cleanup
    shutil.rmtree(optional, ignore_errors=True)

def test_optional_input_2(tmp_path):
    data = {
        'return_output_file': False
    }
    optional = 'optional'

    job = RHJob(node_name="optional", inputs=data, output_directory=optional)
    job.start()
    output = job.wait_for_finish()

    assert not os.path.exists(optional)
    assert output['out_file'] is None

    # Cleanup
    shutil.rmtree(optional, ignore_errors=True)

def test_optional_input_3(tmp_path):
    data = {
        'return_output_file': True
    }
    optional = 'optional'

    job = RHJob(node_name="optional", inputs=data, output_directory=optional)
    job.start()
    output = job.wait_for_finish()

    assert not os.path.exists(optional)
    assert output['out_file'] is None

    # Cleanup
    shutil.rmtree(optional, ignore_errors=True)

def test_optional_input_4(tmp_path):
    data = {}
    optional = 'optional'

    job = RHJob(node_name="optional", inputs=data, output_directory=optional)
    job.start()
    output = job.wait_for_finish()

    assert not os.path.exists(optional)
    assert output['out_file'] is None

    # Cleanup
    shutil.rmtree(optional, ignore_errors=True)

def test_optional_input_5(tmp_path):
    data = {
        'in_file': NII_FILE, 
        'return_output_file': True
    }
    optional = 'optional'

    job = RHJob(node_name="optional", inputs=data, output_directory=optional)
    job.start()
    output = job.wait_for_finish()

    assert os.path.exists(optional)
    assert output['out_file'] == (Path(optional) / "image.nii.gz").absolute()

    # Cleanup
    shutil.rmtree(optional, ignore_errors=True)

def test_optional_input_6(tmp_path):
    data = {
        'in_file': NII_FILE, 
    }
    optional = 'optional'

    job = RHJob(node_name="optional", inputs=data, output_directory=optional)
    job.start()
    output = job.wait_for_finish()

    assert os.path.exists(optional)
    assert output['out_file'] == (Path(optional) / "image.nii.gz").absolute()

    # Cleanup
    shutil.rmtree(optional, ignore_errors=True)