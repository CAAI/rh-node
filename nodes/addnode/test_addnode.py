from rhnode import NodeRunner, new_job

data = {
    "scalar": 1,
    "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"
}

node_jobs = []
for i in range(30):
    job = new_job(check_cache=False)
    job.priority = 3
    node = NodeRunner(
        identifier="add",
        host = "localhost",
        port = 9050,
        inputs = data,
        job = job,
    )
    node.start()
    node_jobs.append(node)