import os
from fastapi.staticfiles import StaticFiles
from .rhjob import JobStatus
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request
from jinja2 import Environment, FileSystemLoader
from .common import *

_TEMPLATES_DIRECTORY = os.path.dirname(__file__) + "/resources/templates"
_STATIC_FILES_DIRECTORY = os.path.dirname(__file__) + "/resources/static"


def setup_frontend_routes(rhnode):
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIRECTORY))

    ## HTML
    def _format_job_result_html(output):
        outs = []
        for key, val in output.dict(exclude_unset=False).items():
            dat = {}
            dat["name"] = key
            dat["val"] = val
            if isinstance(val, str):
                if "/download/" in val:
                    dat["val"] = "download"
                    dat["href"] = val
            outs.append(dat)
        return outs

    def _get_default_context():
        return {
            "node_name": rhnode.name,
        }

    @rhnode.get(rhnode._create_url(""), response_class=HTMLResponse)
    async def show_task_status(request: Request):
        # Load the template from the package
        template = env.get_template("index.html")
        formats = []
        for job_id, job in rhnode.jobs.items():
            formats.append(
                {
                    "task_id": job_id,
                    "status": job.status,
                    "href": rhnode.url_path_for("_show", job_id=job_id),
                }
            )
        html_content = template.render(
            default_context=_get_default_context(), tasks=formats
        )
        return html_content

    @rhnode.get(rhnode._create_url("/jobs/{job_id}"), response_class=HTMLResponse)
    async def _show(job_id: str) -> HTMLResponse:
        job = rhnode.jobs[job_id]
        output = None
        if job.status == JobStatus.Finished:
            output = rhnode._get_output_with_download_links(job_id)
            output = _format_job_result_html(output)

        template = env.get_template("task.html")

        html_content = template.render(
            default_context=_get_default_context(),
            outputs=output,
            queue_status=job.status,
            queue_id=job_id,
        )

        # Return the rendered webpage
        return html_content

    @rhnode.get("/")
    async def redirect_to_manager(request: Request):
        return RedirectResponse(url=rhnode._create_url(""))

    rhnode.mount(
        rhnode._create_url("/static"),
        StaticFiles(directory=_STATIC_FILES_DIRECTORY),
        name="static",
    )
