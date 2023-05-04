from rhnode import NodeRunner, new_job



data = {
    "multiplier": 3,
    "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"
}

for i in range(10):
    job = new_job(check_cache=False,priority=3)
    node = NodeRunner(
        identifier="testnode",
        manager_adress="peyo:9050",
        inputs = data,
        job = job,
        output_directory="output"
    )
    node.start()

node.wait_for_finish()

#hdbet hdctbet, zerodose, deepdixon, totalsegmentator, synthseg