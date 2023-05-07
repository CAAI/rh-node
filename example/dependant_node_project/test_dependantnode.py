from rhnode import NodeRunner, new_job

data = {
    "multiplier": 3,
    "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"
}

job = new_job(check_cache=False,priority=3)
node = NodeRunner(
    identifier="mydependant",
    inputs = data,
    job = job,
)
node.start()

node.wait_for_finish()

