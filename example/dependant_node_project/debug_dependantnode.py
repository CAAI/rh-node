from rhnode import RHJob

data = {"multiplier": 3, "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"}

job = RHJob(
    node_name="dependent",
    inputs=data,
    output_directory=".",
    priority=3,
    check_cache=False,
    included_cuda_device=0,
    resources_included=True,
)

job.start()
job.wait_for_finish()
