from rhnode import NodeRunner, new_job
# Steps:
# 1. Define the inputs to the node you wish to run
# 2. Define the job parameters (priority, whether to check cache)
# 3. Start the node with NodeRunner
# 4. Either wait for the node to finish or stop the node


# JOB parameters
#new_job parameters:
#   check_cache=True - If true, will return the cached result if it exists
#   save_to_cache=True - If true, will save the result to the cache. 
#   priority=[1..5]
#   name="job_name"


### NodeRunner other arguments
#   output_directory=... - Where to save the output. Default is cwd/node_name_[i]/}
#   manager_adress=... - Where to find the manager node. Default is localhost:9050
#   host=... - Hostname of the task node. Default is to ask manager where to run
#   port=... - Port of the task node. Default is to ask manager where to run

# NOTE: manager_adress and host/port are mutually exclusive.

data = {
    "scalar": 3,
    "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"
}

job = new_job(check_cache=False)
job.priority = 3
node = NodeRunner(
    identifier="add",
    inputs = data,
    job = job,
)
node.start() 
output = node.wait_for_finish()

#Alternatively to interrupt the job:
#node.stop()