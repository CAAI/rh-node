#!/usr/bin/env python3

from setuptools import setup, find_packages
from rhnode.version import __version__

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(  
     name='rhnode',
     version=__version__,
     author="Christian Hinge",
     author_email="christian.hinge@regionh.dk",
     description="RHNode used at CAAI",
     long_description=long_description,
     long_description_content_type="text/markdown",
     url="https://github.com/CAAI/rh-node",
     packages=find_packages(),
     include_package_data=True,
     install_requires=[
        'uvicorn',
        'requests',
        'jinja2',
        'pydantic',
        'fastapi',
        'python-multipart',
     ],
     classifiers=[
         'Programming Language :: Python :: 3.8',
         'Programming Language :: Python :: 3.9',
         'Programming Language :: Python :: 3.10',
     ],
 )
