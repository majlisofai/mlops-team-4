"""Stage 1 - ingest: download the pinned source data and record its lineage in MLflow."""

from __future__ import annotations

import hashlib
from pathlib import Path

import mlflow
import pandas as pd
import requests

from pipeline.config import Config
from pipeline.tracking import stage_run

RAW_URL = "https://raw.githubusercontent.com/{repo}/{ref}/{folder}/{file}"


def download(cfg: Config, dest: Path) -> dict:
    """Fetch every source file at the pinned commit. Returns a manifest with URL and sha256 per file."""
    src = cfg.data["source"]
    manifest = {}
    for key, rel in src["files"].items():
        url = RAW_URL.format(repo=src["repo"], ref=src["ref"], folder=src["folder"], file=rel)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        manifest[key] = {
            "file": rel,
            "url": url,
            "sha256": hashlib.sha256(resp.content).hexdigest(),
            "bytes": len(resp.content),
        }
    return manifest


def run(cfg: Config) -> dict:
    src = cfg.data["source"]
    raw = cfg.work_dir / "raw"
    with stage_run(cfg, "ingest") as run:
        manifest = download(cfg, raw)
        history = pd.read_csv(raw / src["files"]["history"])

        mlflow.log_params({"source_repo": src["repo"], "source_ref": src["ref"], "source_folder": src["folder"]})
        mlflow.log_metrics({"history_rows": len(history), "history_columns": history.shape[1]})
        mlflow.log_input(
            mlflow.data.from_pandas(
                history, source=manifest["history"]["url"], name=f"{cfg.dataset}-history", targets=cfg.target
            ),
            context="source",
        )
        mlflow.log_dict(manifest, "manifest.json")
        mlflow.log_artifacts(str(raw), "raw")

    cfg.save_state(ingest_run_id=run.info.run_id, data_sha256=manifest["history"]["sha256"])
    return {
        "history_rows": len(history),
        "summary": f"{len(history):,} rows from `{src['repo']}@{src['ref'][:7]}`",
    }
