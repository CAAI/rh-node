from rhnode import RHNode
from pydantic import BaseModel, FilePath
from typing import Optional
import shutil


class InputsOutputDirectory(BaseModel):
    in_file: FilePath
    return_output_file: bool = True


class OutputsOutputDirectory(BaseModel):
    out_file: Optional[FilePath] = None


class OutputDirectoryNode(RHNode):
    input_spec = InputsOutputDirectory
    output_spec = OutputsOutputDirectory
    name = "outputdirectory"
    requires_gpu = False
    required_gb_gpu_memory = 0
    required_num_threads = 1
    required_gb_memory = 1

    def process(inputs, job):
        outargs = {}

        if inputs.return_output_file:
            outargs['out_file'] = job.directory / "image.nii.gz"
            shutil.copyfile(inputs.in_file, outargs['out_file'])
            
        return OutputsOutputDirectory(**outargs)

app = OutputDirectoryNode()
