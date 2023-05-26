1. clone the repo
2. create a .env file in the repo root. This should contain variables that define the hardware of your device:

    ```python
    RH_GPU_MEM=8
    RH_NUM_THREADS=16
    RH_MEMORY=12
    ```
3. create changes
4. optionally run pytest (see tests/test_docker.py for details)