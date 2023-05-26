from rhnode import RHNode, RHJob
from pydantic import BaseModel, FilePath
import nibabel as nib


class InputsDependent(BaseModel):
    multiplier: int
    in_file: FilePath


class OutputsDependent(BaseModel):
    message: str
    img1: FilePath
    img2: FilePath


class MyDependentNode(RHNode):
    input_spec = InputsDependent
    output_spec = OutputsDependent
    name = "dependent"

    required_gb_gpu_memory = 1
    required_num_threads = 1
    required_gb_memory = 1

    def process(inputs, job):
        add_inputs = {"scalar": 1, "in_file": inputs.in_file, "sleep_time": 0}
        add_1_node = RHJob.from_parent_job("add", add_inputs, job)

        add_inputs = {"scalar": 1, "in_file": inputs.in_file, "sleep_time": 0}
        add_2_node = RHJob.from_parent_job("add", add_inputs, job)

        # Start nodes in parallel
        add_1_node.start()
        add_2_node.start()

        # Wait for node 1 to finish and multiply it by the multiplier constant
        outputs_1 = add_1_node.wait_for_finish()
        img = nib.load(outputs_1["out_file"])
        arr = img.get_fdata() * inputs.multiplier
        img = nib.Nifti1Image(arr, img.affine, img.header)
        outpath = job.directory / "img1.nii.gz"
        img.to_filename(outpath)

        # Wait for node 2 to finish and leave it as is
        outputs_2 = add_2_node.wait_for_finish()

        return OutputsDependent(
            message="Hello World", img1=outpath, img2=outputs_2["out_file"]
        )


app = MyDependentNode()
