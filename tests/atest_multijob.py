# %%

## Not to be run via pytest as of now
import glob
import os

from rhnode import RHJob, MultiJobRunner
import os
import json
import datetime
import nibabel as nib
from pathlib import Path
import re

ROOT = "/depict/data/quadra_fdg"

jobs = []

for i in range(500):
    inputs = {
        "scalar": 2,
        "in_file": "/homes/hinge/Projects/rh-node/tests/data/mr.nii.gz",
        "out_file": "out.nii.gz",
    }
    job = RHJob(
        node_name="add",
        manager_address="localhost:9050",
        inputs=inputs,
        check_cache=False,
    )

    jobs.append(job)

job_runner = MultiJobRunner(jobs, queue_length=8)
job_runner.start()

# %%
