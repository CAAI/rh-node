from rhnode import RHJob

# NOTE: manager_adress and host/port are mutually exclusive.

data = {
    "scalar": 3,
    "in_file": "/homes/hinge/Projects/rh-node/tests/data/mr.nii.gz",
    "sleep_time": 0,
    "throw_error": False,
}

node = RHJob(
    node_name="add",
    inputs=data,
    # manager_adress="tower:9050",
    resources_included=True,
    # included_cuda_device=0,
    node_address="localhost:8009",
    # port="9050",
    node_address="localhost:8009",
    output_directory=".temp_output",
    save_non_files=True,
    check_cache=False,
)
node.start()
output = node.wait_for_finish()
