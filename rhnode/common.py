from pydantic import BaseModel, FilePath, DirectoryPath, create_model
from pathlib import Path
from typing import Type, Union
from enum import Enum
import os


class JobMetaData(BaseModel):
    device: Union[None, int]
    check_cache: bool = True
    save_to_cache: bool = True
    priority: int = 2
    directory: Union[None, DirectoryPath] = None
    resources_included: bool = False


class Node(BaseModel):
    name: str
    last_heard_from: float
    gpu_gb_required: float
    cores_required: int
    memory_required: int


class JobRequest(BaseModel):
    job_id: str
    priority: int
    required_gpu_mem: int
    required_cores: int
    required_memory: int


class QueueStatus(Enum):
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


class QueueResponse(BaseModel):
    status: QueueStatus  # Waiting for GPU, Running, Finished, Error
    output: BaseModel = None
    input: BaseModel = None
    input_directory: DirectoryPath = None
    error: Error = None


def is_relative_to(a, b):
    assert isinstance(a, Path)
    assert isinstance(b, Path)
    try:
        a.relative_to(b)
        return True
    except ValueError:
        return False


def create_file_name_from_key(key_name, file_name):
    if "." in os.path.basename(file_name):
        ending = os.path.basename(file_name).split(".")[1:]
        ending = ".".join(ending)
        return f"{key_name}.{ending}"
    return key_name


def create_filepath_as_string_model(cls: Type[BaseModel]) -> Type[BaseModel]:
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            fields[field_name] = (str, field.field_info)
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "URL", **fields, __base__=cls)


def create_relaxed_filepath_model(cls: Type[BaseModel]) -> Type[BaseModel]:
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            fields[field_name] = (Union[None, FilePath], field.field_info)
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "RELAX", **fields, __base__=cls)


def create_model_no_files(cls: Type[BaseModel]) -> Type[BaseModel]:
    fields = {}
    for field_name, field in cls.__fields__.items():
        if issubclass(field.type_, FilePath):
            continue
        else:
            fields[field_name] = (field.type_, field.field_info)
    return create_model(cls.__name__ + "INIT", **fields)
