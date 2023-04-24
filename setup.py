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
     packages=find_packages(),#["rhnode"],
    # package_dir={
    #'rhnode': 'rhnode'},
     install_requires=[
         'pyminc',
         'pydicom',
         'opencv-python',
         'matplotlib',
         'pandas',
         'nipype',
         'scikit-image',
         'nibabel',
         'pydantic',
         'fastapi',
         'jinja2'
     ],
     classifiers=[
         'Programming Language :: Python :: 3.8',
     ],
 )
