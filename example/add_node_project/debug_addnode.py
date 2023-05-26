from rhnode import RHJob

# NOTE: manager_adress and node_address are mutually exclusive.

data = {
    "scalar": 3,
    "in_file": "/homes/hinge/Projects/rh-node/tests/data/mr.nii.gz",
}

node = RHJob(
    node_name="add",
    inputs=data,
    node_address="localhost:8030",
    output_directory=".",
    resources_included=True,
    included_cuda_device=0,  # if applicable
    priority=3,
    check_cache=False,
)
# Wait for the node to finish
node.start()

output = node.wait_for_finish()

# Alternatively to interrupt the job:
# node.stop()
