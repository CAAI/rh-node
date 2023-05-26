from rhnode import RHJob

data = {"multiplier": 3, "in_file": "/homes/hinge/Projects/rh-node/test/mr.nii.gz"}

job = RHJob(node_name="dependent", inputs=data, output_directory="output")

job.start()

job.wait_for_finish()

# hdbet hdctbet, zerodose, deepdixon, totalsegmentator, synthseg
