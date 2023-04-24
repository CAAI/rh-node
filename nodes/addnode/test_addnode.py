from rhnode import NodeRunner, new_job


data = {
    "scalar": 1,
    "in_file": "/homes/hinge/Projects/rh-node/nodedata/test/mr.nii.gz"
}

job = new_job(prefix="testadd")

node = NodeRunner(
    identifier="add",
    host = "localhost",
    port = 8009,
    inputs = data,
    job = job
)

node.start()