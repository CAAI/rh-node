from rhnode import RHNode
from pydantic import BaseModel, FilePath
import nibabel as nib
import time


class InputsAdd(BaseModel):
    scalar: int
    sleep_time: int = 5
    throw_error: bool = False
    in_file: FilePath
    check_device_allocated: int = -1


class OutputsAdd(BaseModel):
    out_file: FilePath
    out_message: str


class AddNode(RHNode):
    input_spec = InputsAdd
    output_spec = OutputsAdd
    name = "add"
    requires_gpu = True
    required_gb_gpu_memory = 3
    required_num_threads = 3
    required_gb_memory = 3

    def process(inputs, job):
        img = nib.load(inputs.in_file)
        arr = img.get_fdata() + inputs.scalar
        img = nib.Nifti1Image(arr, img.affine, img.header)
        outpath = job.directory / "added.nii.gz"
        img.to_filename(outpath)
        time.sleep(inputs.sleep_time)

        if inputs.throw_error:
            raise AssertionError("This an error caused by throw_error=True")

        if inputs.check_device_allocated != -1:
            assert (
                inputs.check_device_allocated == job.device
            ), "Device allocated is not the same as the one requested"

        return OutputsAdd(out_file=outpath, out_message="this worked")


app = AddNode()
