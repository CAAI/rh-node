import multiprocessing
from abc import ABC, abstractmethod
from pydantic import BaseModel, FilePath
import requests
import asyncio
import uuid
from ..rhjob import *
from ..common import *
from fastapi.responses import FileResponse, JSONResponse
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from ..rhprocess import RHProcess
import traceback
from fastapi import Response
from fastapi import HTTPException
from ..email import EmailSender
import datetime
from fastapi import Request
from ..version import __version__


def setup_api_routes(rhnode):
    """Setup the API routes for the node. See frontend.py for the frontend routes."""

    @rhnode.post(rhnode._create_url("/jobs"))
    async def _post_new_job(inputs: rhnode.input_spec_no_file) -> str:
        job_id = rhnode.CREATE_JOB(inputs)
        return job_id

    @rhnode.post(rhnode._create_url("/jobs/{job_id}/start"))
    async def START_JOB(
        job_id: str, job_meta_data: JobMetaData, background_tasks: BackgroundTasks
    ) -> Response:
        job_obj = rhnode.get_job_by_id(job_id)
        rhnode._ensure_job_status(job_obj.status, JobStatus.Preparing)
        if not job_obj.is_ready_to_run():
            raise HTTPException(
                status_code=400,
                detail="Job is not ready to run. Some files are likely missing.",
            )
        background_tasks.add_task(job_obj.run, job_meta_data)
        return Response(status_code=204)

    @rhnode.get(rhnode._create_url("/jobs/{job_id}/status"))
    async def _get_job_status(job_id: str) -> JobStatus:
        return rhnode.get_job_by_id(job_id).status

    @rhnode.get(rhnode._create_url("/jobs/{job_id}/data"))
    async def _get_job_data_download_urls(job_id: str) -> rhnode.output_spec_url:
        return rhnode._get_output_with_download_links(job_id)

    @rhnode.get(rhnode._create_url("/jobs/{job_id}/error"))
    def _get_job_error(job_id: str):
        job = rhnode.get_job_by_id(job_id)
        rhnode._ensure_job_status(job.status, [JobStatus.Cancelled, JobStatus.Error])
        return job.error

    @rhnode.post(rhnode._create_url("/jobs/{job_id}/stop"))
    def _stop_task(job_id: str):
        job = rhnode.get_job_by_id(job_id)
        if job.status not in [
            JobStatus.Finished,
            JobStatus.Cancelled,
            JobStatus.Cancelling,
            JobStatus.Error,
        ]:
            job.stop()
            return Response(status_code=204)

        return Response(status_code=200, content="Job is already in terminal phase")

    @rhnode.post(rhnode._create_url("/jobs/{job_id}/delete"))
    async def _delete_job(job_id: str):
        """Delete a job from the node."""
        job = rhnode.get_job_by_id(job_id)
        rhnode._delete_job(job_id)

    @rhnode.get(rhnode._create_url("/jobs/{job_id}/download/{filename}"))
    def _get_file(job_id, filename):
        job = rhnode.get_job_by_id(job_id)
        rhnode._ensure_job_status(job.status, JobStatus.Finished)
        if not filename in rhnode.output_spec.__fields__:
            raise HTTPException(
                status_code=404,
                detail="The requested file key {} is invalid.".format(filename),
            )
        try:
            fname = job.output.dict()[filename]
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail="The requested file corresponding to key {} could not be found.".format(
                    filename
                ),
            )
        return FileResponse(fname, filename=create_file_name_from_key(filename, fname))

    @rhnode.get(rhnode._create_url("/filename_keys"))
    async def _get_file_keys():
        return rhnode.input_file_keys

    @rhnode.get(rhnode._create_url("/keys"))
    async def _get_keys():
        return {
            "output_keys": list(rhnode.output_spec.__fields__.keys()),
            "input_keys": list(rhnode.input_spec.__fields__.keys()),
        }

    @rhnode.post(rhnode._create_url("/cli/parse"))
    async def _parse_cli_args(cli: list):
        try:
            return rhnode.parse_cli_args(cli)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @rhnode.get(rhnode._create_url("/cli/help"))
    async def _get_job_input():
        return rhnode.help_cli_args()

    @rhnode.post(rhnode._create_url("/jobs/{job_id}/upload"))
    async def _upload(
        job_id: str,
        file: UploadFile = File(...),
        key: str = Form(...),
    ):
        job = rhnode.get_job_by_id(job_id)
        rhnode._ensure_job_status(job.status, JobStatus.Preparing)

        """Upload an input file to a job. The key must be one of the file keys."""

        if not key in rhnode.input_file_keys:
            raise HTTPException(
                status_code=404,
                detail="The requested file key {} is invalid.".format(key),
            )
        # The outer with statement is to ensure that the file is validated after upload
        with job.upload_file(key, file.filename) as fpath:
            with open(fpath, "wb") as f:
                f.write(await file.read())

        return Response(status_code=204)

    ### OTHER
    @rhnode.on_event("startup")
    async def register_on_startup():
        # print(multiprocessing.get_start_method())
        """Looks for manager node at startup and initializes multiprocessing module"""
        # if not os.environ.get("PYTEST", False):
        multiprocessing.set_start_method("spawn")
        asyncio.create_task(rhnode._register_with_manager())

    @rhnode.exception_handler(500)
    async def internal_exception_handler(request: Request, exc: Exception):
        if rhnode.email_sender:
            rhnode.email_sender.send_email_exception(
                rhnode.name, rhnode.host_name, datetime.datetime.now()
            )

        return JSONResponse(
            status_code=500, content={"code": 500, "msg": "Internal Server Error"}
        )

    @rhnode.on_event("startup")
    async def start_cleaning_loop():
        asyncio.create_task(rhnode._delete_expired_jobs_loop())
