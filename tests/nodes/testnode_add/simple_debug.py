from rhnode import RHJob


# NOTE: manager_adress and host/port are mutually exclusive.

data = {
    "scalar": 3,
    "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz",
    "sleep_time": 2,
    "throw_error": False,
}

node = RHJob(
    node_name="add",
    inputs=data,
    # manager_adress="tower:9050",
    resources_included=True,
    # included_cuda_device=0,
    # host="localhost:9050",
    # port="9050",
    check_cache=False,
)
node.start()
output = node.wait_for_finish()

# Alternatively to interrupt the job:
# node.stop()
