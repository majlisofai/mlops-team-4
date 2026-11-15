"""Read-only views of the team's MLflow server, as Markdown tables.

python .claude/skills/mlflow-explore/scripts/mlflow_report.py runs [--limit 10]     latest pipeline runs
python .claude/skills/mlflow-explore/scripts/mlflow_report.py compare [--limit 10]  train + evaluate metrics side by side
python .claude/skills/mlflow-explore/scripts/mlflow_report.py models                registry versions, aliases, tags
python .claude/skills/mlflow-explore/scripts/mlflow_report.py run <run_id>          one run: tags, params, metrics, artifacts
add --dataset f1|spl to override team.yaml
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from mlflow import MlflowClient  # noqa: E402
from mlflow.exceptions import MlflowException  # noqa: E402

from pipeline.config import DATASETS, load_config  # noqa: E402

METRICS = ["cv_accuracy_mean", "holdout_accuracy", "baseline_accuracy", "accuracy_lift", "holdout_roc_auc"]


def table(headers: list[str], rows: list[list]) -> str:
    fmt = [f"{v:.4f}" if isinstance(v, float) else ("" if v is None else str(v)) for row in rows for v in row]
    cells = [fmt[i : i + len(headers)] for i in range(0, len(fmt), len(headers))]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in cells])


def when(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%M")


def experiment_id(client: MlflowClient, name: str) -> str:
    exp = client.get_experiment_by_name(name)
    if exp is None:
        sys.exit(f"No experiment {name!r} yet - run `make pipeline` first.")
    return exp.experiment_id


def stage_runs(client: MlflowClient, exp_id: str, stage: str, limit: int):
    return client.search_runs([exp_id], f"tags.stage = '{stage}'", order_by=["attributes.start_time DESC"], max_results=limit)


def cmd_runs(client, cfg, args):
    runs = stage_runs(client, experiment_id(client, cfg.experiment), "pipeline", args.limit)
    rows = [
        [
            r.info.run_id[:8],
            when(r.info.start_time),
            r.info.status,
            r.data.tags.get("runs_on"),
            r.data.tags.get("git_sha", "")[:7],
        ]
        for r in runs
    ]
    print(f"## Pipeline runs - experiment `{cfg.experiment}`\n")
    print(table(["run", "started (UTC)", "status", "runs_on", "git"], rows))


def cmd_compare(client, cfg, args):
    exp_id = experiment_id(client, cfg.experiment)
    evaluations = {r.data.tags.get("mlflow.parentRunId"): r for r in stage_runs(client, exp_id, "evaluate", args.limit * 2)}
    rows = []
    for train in stage_runs(client, exp_id, "train", args.limit):
        ev = evaluations.get(train.data.tags.get("mlflow.parentRunId"))
        metrics = train.data.metrics | (ev.data.metrics if ev else {})
        params = {k.removeprefix("model."): v for k, v in train.data.params.items() if k.startswith("model.")}
        rows.append(
            [train.info.run_id[:8], when(train.info.start_time), train.data.params.get("model_type"), params]
            + [metrics.get(m) for m in METRICS]
            + [ev.data.tags.get("quality_gate") if ev else None]
        )
    print(f"## Train + evaluate runs - experiment `{cfg.experiment}`\n")
    print(table(["train run", "started (UTC)", "model", "params", *METRICS, "gate"], rows))


def cmd_models(client, cfg, args):
    try:
        model = client.get_registered_model(cfg.model_name)
    except MlflowException:
        sys.exit(f"No registered model {cfg.model_name!r} yet - a run must pass the quality gate first.")
    aliases = {}
    for alias, version in model.aliases.items():
        aliases.setdefault(str(version), []).append(f"@{alias}")
    versions = sorted(client.search_model_versions(f"name = '{cfg.model_name}'"), key=lambda v: -int(v.version))
    rows = [
        [
            v.version,
            " ".join(aliases.get(v.version, [])),
            when(v.creation_timestamp),
            v.tags.get("model_type"),
            v.tags.get("holdout_accuracy"),
            v.tags.get("git_sha", "")[:7],
            v.run_id[:8] if v.run_id else "",
        ]
        for v in versions
    ]
    print(f"## Registered model `{cfg.model_name}`\n")
    print(table(["version", "aliases", "created (UTC)", "model", "holdout_accuracy", "git", "run"], rows))


def cmd_run(client, cfg, args):
    run = client.get_run(args.run_id)
    print(f"## Run `{run.info.run_name}` ({run.info.run_id}) - {run.info.status}\n")
    for title, data in (("Tags", run.data.tags), ("Params", run.data.params), ("Metrics", run.data.metrics)):
        shown = {k: v for k, v in sorted(data.items()) if not k.startswith("mlflow.")}
        print(f"### {title}\n\n" + (table(["key", "value"], [[k, v] for k, v in shown.items()]) if shown else "(none)") + "\n")
    print("### Artifacts\n\n" + "\n".join(f"- {a.path}" for a in client.list_artifacts(run.info.run_id)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("view", choices=["runs", "compare", "models", "run"])
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dataset", choices=DATASETS)
    args = parser.parse_args()
    if args.view == "run" and not args.run_id:
        parser.error("run needs a run_id")
    cfg = load_config(dataset=args.dataset)
    {"runs": cmd_runs, "compare": cmd_compare, "models": cmd_models, "run": cmd_run}[args.view](MlflowClient(), cfg, args)


if __name__ == "__main__":
    main()
