from rhnode import RHNode
from pydantic import BaseModel, FilePath
from typing import Optional
import shutil


class InputsOptional(BaseModel):
    in_file: Optional[FilePath] = None
    return_output_file: Optional[bool] = True


class OutputsOptional(BaseModel):
    out_file: Optional[FilePath] = None


class OutputOptional(RHNode):
    input_spec = InputsOptional
    output_spec = OutputsOptional
    name = "optional"
    requires_gpu = False
    required_gb_gpu_memory = 0
    required_num_threads = 1
    required_gb_memory = 1

    def process(inputs, job):
        outargs = {}

        if inputs.return_output_file and inputs.in_file is not None:
            outargs['out_file'] = job.directory / "image.nii.gz"
            shutil.copyfile(inputs.in_file, outargs['out_file'])
            
        return OutputsOptional(**outargs)

app = OutputOptional()
