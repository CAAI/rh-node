"""Common definitions used by RHNode, RHJob, RHProcess and RHManager"""
from pydantic import BaseModel, FilePath, DirectoryPath, create_model
from pathlib import Path
from typing import Type, Union
from enum import Enum
import os


class JobCancelledError(Exception):
    """Raised when a job is cancelled by the user"""

    pass


class JobFailedError(Exception):
    """Raised when an error occurs within the Process function of a node"""

    pass


class JobMetaData(BaseModel):
    """The 'job' object passed to the process function of a node"""

    device: Union[None, int]
    check_cache: bool = True
    save_to_cache: bool = True
    priority: int = 2
    directory: Union[None, DirectoryPath] = None
    resources_included: bool = False


class NodeMetaData(BaseModel):
    """Meta data structure used to tell the manager about the node"""

    name: str
    last_heard_from: float
    gpu_gb_required: float
    threads_required: int
    memory_required: int


class QueueRequest(BaseModel):
    """Request sent by the node to the manager when it wants enter the resource queue"""

    job_id: str
    priority: int
    required_gpu_mem: int
    required_threads: int
    required_memory: int


class JobStatus(Enum):
    """Each RHProcess has a status attribute"""

    Preparing = -1  # Files are being uploaded
    Initializing = 0  # The job is being initialized
    Queued = 1  # THe job is queued
    Running = 2  # The job is running
    Finished = 3  # The job is finished
    Error = 4  # The job has encountered an error
    Cancelling = 5  # The job is being cancelled
    Cancelled = 6  # The job has been cancelled


class Error(BaseModel):
    error: str
    traceback: str


def is_relative_to(a, b):
    """Check if path a is relative to path b"""
    assert isinstance(a, Path)
    assert isinstance(b, Path)
    try:
        a.relative_to(b)
        return True
    except ValueError:
        return False


def create_file_name_from_key(key_name, file_name):
    """Create a filename from the pydantic attribute name and a file ending"""
    # if "." in os.path.basename(file_name):
    #     ending = os.path.basename(file_name).split(".")[1:]
    #     ending = ".".join(ending)
    #     return f"{key_name}.{ending}"
    return os.path.basename(file_name)


def create_filepath_as_string_model(cls: Type[BaseModel]) -> Type[BaseModel]:
    """Create a model that has all FilePath fields replaced with strings.
    This is useful when we want a "download" link to the file instead of the file itself.
    """

    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            fields[field_name] = (str, field.field_info)
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "URL", **fields, __base__=cls)


def create_relaxed_filepath_model(cls: Type[BaseModel]) -> Type[BaseModel]:
    """Create a model that has all FilePath fields replaced with Optional FilePath fields.
    This is used while RHJob is uploading input files one by one."""
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            fields[field_name] = (Union[None, FilePath], field.field_info)
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "RELAX", **fields, __base__=cls)


def create_model_no_files(cls: Type[BaseModel]) -> Type[BaseModel]:
    """Create a model that removes all FilePath fields. This is useful when returning
    the result of a finished job. Due to HTTP limitations, we cannot return files directly.
    They are downloaded instead."""
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            continue
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "INIT", **fields)


def validate_input_output_spec(input_spec, output_spec):
    input_keys = list(input_spec.__fields__.keys())
    output_keys = list(output_spec.__fields__.keys())

    combined = input_keys + output_keys
    if len(combined) != len(set(combined)):
        raise ValueError(
            "Input spec and output spec must not have overlapping key names"
        )
