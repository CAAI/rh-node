from rhnode import NodeRunner, new_job

# Define the inputs to the node you wish to run
data = {
    "scalar": 3,
    "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"
}

# Define the job parameters (priority, whether to check cache)
job = new_job(check_cache=True)
job.device=0

# Start the node with NodeRunner
node = NodeRunner(
    identifier="add",
    host = "localhost",
    port = 8010,
    inputs=data,
    job=job,
    resources_included=True
)
node.start()

# Wait for the node to finish
output = node.wait_for_finish()

# Alternatively, to interrupt the job:
# node.stop()