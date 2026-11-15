"""MLflow helpers shared by every stage."""

from __future__ import annotations

import contextlib
import os
import subprocess
import time

import mlflow
import requests
from mlflow.entities import Run

from pipeline.config import Config


def wait_for_server(timeout: int = 90) -> None:
    """The MLflow container can still be starting when the Codespace opens."""
    uri = mlflow.get_tracking_uri()
    if not uri.startswith("http"):
        return
    deadline = time.time() + timeout
    while True:
        try:
            if requests.get(f"{uri}/health", timeout=3).ok:
                return
        except requests.RequestException:
            pass
        if time.time() > deadline:
            raise RuntimeError(f"MLflow server is not reachable at {uri}")
        time.sleep(2)


def git_sha() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def runs_on() -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github-actions"
    if os.environ.get("CODESPACES") == "true":
        return "codespaces"
    return "local"


@contextlib.contextmanager
def stage_run(cfg: Config, stage: str):
    """One MLflow run per stage. Nested under the pipeline run when `python -m pipeline all` is used."""
    mlflow.set_experiment(cfg.experiment)
    nested = mlflow.active_run() is not None
    with mlflow.start_run(run_name=stage, nested=nested) as run:
        mlflow.set_tags(
            {
                "stage": stage,
                "team": cfg.team_name,
                "dataset": cfg.dataset,
                "git_sha": git_sha(),
                "runs_on": runs_on(),
                "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            }
        )
        yield run


def ui_url(path: str = "") -> str:
    """Browser address of the MLflow UI: the forwarded port in Codespaces, localhost elsewhere."""
    name = os.environ.get("CODESPACE_NAME")
    domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    base = f"https://{name}-5000.{domain}" if name and domain else "http://localhost:5000"
    return base + path


def run_url(run: Run) -> str:
    return ui_url(f"/#/experiments/{run.info.experiment_id}/runs/{run.info.run_id}")
