from rhnode import RHNode
from pydantic import BaseModel, FilePath
import subprocess



class HDBetInput(BaseModel):
    mr:FilePath

class HDBetOutput(BaseModel):
    masked_mr:FilePath
    mask:FilePath

class HDBetNode(RHNode):
    input_spec = HDBetInput
    output_spec = HDBetOutput
    name = "hdbet"

    def process(inputs, job):

        out_mri = job.directory / "mri_masked.nii.gz"
        out_mask= job.directory / "mri_masked_mask.nii.gz"
        
        cmd = ["hd-bet", "-i", str(inputs.mr), "-o", str(out_mri)]

        output = subprocess.check_output(cmd, text=True)

        return HDBetOutput(masked_mr=out_mri, mask=out_mask)


app = HDBetNode()

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="localhost",port=8000)