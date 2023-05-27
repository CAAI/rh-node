from rhnode import RHJob

# NOTE: manager_adress and host/port are mutually exclusive.

data = {
    "scalar": 3,
    "in_file": "/homes/hinge/Projects/rh-node/tests/data/mr.nii.gz",
    "out_file": "added.nii.gz",
}

node = RHJob(
    node_name="add",
    inputs=data,
    # manager_adress="tower:9050",
    resources_included=True,
    node_address="localhost:8009",
    output_directory=".temp_output",
    save_non_files=True,
    check_cache=False,
)
node.start()
output = node.wait_for_finish()
