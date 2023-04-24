from rhnode import NodeRunner, new_job


data = {
    "scalar": 1,
    "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"
}

job = new_job()

node = NodeRunner(
    identifier="add",
    host = "localhost",
    port = 8009,
    inputs = data,
    job = job,
)

node.start()
output = node.wait_for_finish()

print(output)