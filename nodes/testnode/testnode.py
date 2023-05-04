from rhnode import RHNode, NodeRunner
from pydantic import BaseModel, FilePath
import nibabel as nib

class MyInputs(BaseModel):
    multiplier: int
    in_file: FilePath

class MyOutputs(BaseModel):
    message: str
    img1: FilePath
    img2: FilePath

class MyDependantNode(RHNode):
    input_spec = MyInputs
    output_spec = MyOutputs
    name = "testnode"
    
    required_gb_gpu_memory = 1
    required_num_processes = 1
    required_gb_memory = 1    
    
    def process(inputs, job):
        
        add_inputs = {"scalar": 1,"in_file": inputs.in_file}
        add_1_node = NodeRunner("add", add_inputs, job)
        
        add_inputs = {"scalar": 1,"in_file": inputs.in_file}
        add_2_node = NodeRunner("add", add_inputs, job)
        
        # Start nodes in parallel
        add_1_node.start()
        add_2_node.start()

        # Wait for node 1 to finish and multiply it by the multiplier constant
        outputs_1 = add_1_node.wait_for_finish()
        img = nib.load(outputs_1["out_file"])
        arr = img.get_fdata()*inputs.multiplier
        img = nib.Nifti1Image(arr, img.affine, img.header)
        outpath = job.directory / "img1.nii.gz"
        img.to_filename(outpath)
        
        #Wait for node 2 to finish and leave it as is
        outputs_2 = add_2_node.wait_for_finish()
        
        return MyOutputs(message="Hello World", img1=outpath, img2=outputs_2["out_file"])
    

app = MyDependantNode()
