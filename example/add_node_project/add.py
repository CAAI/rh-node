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
