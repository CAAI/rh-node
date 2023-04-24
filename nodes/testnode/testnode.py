from rhnode import RHNode
from pydantic import BaseModel, FilePath
import nibabel as nib
import time
from typing import Optional
import asyncio
from rhnode import NodeRunner
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

class TestInputs(BaseModel):
    multiplier: int
    in_file: FilePath = "/homes/hinge/Projects/rhnode/testdata/test22.nii"
class TestOutputs(BaseModel):
    message: str
    img1: FilePath
    img2: FilePath

class TestNode(RHNode):
    input_spec = TestInputs
    output_spec = TestOutputs
    name = "testnode"
    requires_gpu = True
    
    def process(inputs, job):

        add_inputs = {"scalar": 1,"in_file": inputs.in_file}        
        add_1_node = NodeRunner("add", add_inputs, job)
        
        add_inputs = {"scalar": 1,"in_file": inputs.in_file}
        add_2_node = NodeRunner("add", add_inputs, job)
        
        # Start nodes in parallel
        add_1_node.start()
        add_2_node.start()

        # Wait for node 1 to finish and multiply it
        outputs_1 = add_1_node.wait_for_finish()
        img = nib.load(outputs_1["out_file"])
        arr = img.get_fdata()*inputs.multiplier
        img = nib.Nifti1Image(arr, img.affine, img.header)
        outpath = job.directory / "img1.nii.gz"
        img.to_filename(outpath)
        
        #Wait for node 2 to finish and multiply it
        outputs_2 = add_2_node.wait_for_finish()

        return TestOutputs(message="Hello World", img1=outpath, img2=outputs_2["out_file"])
    

app = TestNode()
