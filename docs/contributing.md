## Contributing

### Steps
1. Create/checkout the development branch of the next version, following the version scheme below (e.g. `dev/1.2.0`). 

   If branch exists on github, make sure to pull latest changes: `git pull`
2. Add your changes
3. Add pytest functions under tests to check any added functionality
4. Make sure you create a file under tests/data/mr.nii.gz
5. On one terminal, in the `tests` dir, run `docker compose up --build`

   On another terminal run `pytest <test_YOURTESTFILE.py>` to run your added tests only, or `pytest` to run all tests
5. Commit and push changes to github
6. **[Optional]** If you wish to make the changes available to rh-library nodes, then create release with tag following the versioning below (e.g. `dev/1.2.0-a.2` if -a.1 was the last alpha release). The docker image will be build and pushed to docker hub.

### Versioning
Version naming follows `major.minor.patch` where each new release has an increment to minor version, and any release with smaller bugfixes an increment to patch version. New functions are implemented in the next versions dev branch and releases are tagged with with `-a.X` where X is a running counter. 
Example: If the current version is `v1.1.2` then the next patch with bugfixes implemented in the `main` branch has to be named `v1.1.3`. New functions are implemented in the `dev/v1.2.0` branch and releases are tagged with `v1.2.0-a.X` where again X is a running counter from 1. At some point the dev branch becomes the next version (`v1.2.0`) and a new branch (`dev/v1.3.0`) is created.

Releases in RH-Library are tagged with the version of rh-node that it has been build against, so e.g. `hdbet-v1.1.0` that is build against `rhnode v1.1.2` is tagged `hdbet-v1.1.0_rhnode1.1.2`. <b>Note:</b> Alpha releases must be tagged without the hyphen since this is used to automatically tag versions on dockerhub, so the correct name would be e.g., `hdbet-v1.1.0_rhnode1.2.0a.1` rather than `hdbet-v1.1.0_rhnode1.2.0-a.1`.

### Legacy doc (could be deleted?)
1. clone the repo
2. create a .env file in the repo root. This should contain variables that define the hardware of your device:

    ```python
    RH_GPU_MEM=8
    RH_NUM_THREADS=16
    RH_MEMORY=12
    ```
3. create changes
4. optionally run pytest (see tests/test_docker.py for details)
