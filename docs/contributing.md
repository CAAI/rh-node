1. clone the repo
2. create a .env file in the repo root. This should contain variables that define the hardware of your device:

    ```python
    RH_GPU_MEM=8
    RH_NUM_THREADS=16
    RH_MEMORY=12
    ```
3. create changes
4. optionally run pytest (see tests/test_docker.py for details)

## Contributing

### Versioning
Version naming follows `major.minor.patch` where each new release has an increment to minor version, and any release with smaller bugfixes an increment to patch version. New functions are implemented in the next versions dev branch and releases are tagged with with `-a.X` where X is a running counter. 
Example: If the current version is `v1.1.2` then the next patch with bugfixes implemented in the `main` branch has to be named `v1.1.3`. New functions are implemented in the `dev/v1.2.0` branch and releases are tagged with `v1.2.0-a.X` where again X is a running counter from 1. At some point the dev branch becomes the next version (`v1.2.0`) and a new branch (`dev/v1.3.0`) is created.

Releases in RH-Library are tagged with the version of rh-node that it has been build against, so e.g. `hdbet-v1.1.0` that is build against `rhnode v1.1.2` is tagged `hdbet-v1.1.0_rhnode1.1.2`. <b>Note:</b> Alpha releases must be tagged without the hyphen since this is used to automatically tag versions on dockerhub, so the correct name would be e.g., `hdbet-v1.1.0_rhnode1.2.0a.1` rather than `hdbet-v1.1.0_rhnode1.2.0-a.1`.
