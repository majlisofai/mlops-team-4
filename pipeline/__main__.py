"""Command line for the pipeline.

python -m pipeline all               every stage, as one MLflow parent run with a nested run per stage
python -m pipeline <stage>           one stage: ingest | validate | prepare | train | evaluate | register | predict | monitor
python -m pipeline predict --endpoint http://localhost:5001/invocations
python -m pipeline all --dataset spl override the dataset in team.yaml
"""

from __future__ import annotations

import argparse
import sys

from pipeline import evaluate, ingest, monitor, predict, prepare, register, train, validate
from pipeline.config import DATASETS, Config, load_config
from pipeline.tracking import run_url, stage_run, ui_url, wait_for_server

STAGES = {
    "ingest": ingest.run,
    "validate": validate.run,
    "prepare": prepare.run,
    "train": train.run,
    "evaluate": evaluate.run,
    "register": register.run,
    "predict": predict.run,
    "monitor": monitor.run,
}


def write_summary(cfg: Config, results: dict, url: str) -> str:
    lines = [
        f"## MLOps pipeline - `{cfg.team_name}` / `{cfg.dataset}`",
        "",
        "| Stage | Result |",
        "|---|---|",
        *[f"| {stage} | {result['summary']} |" for stage, result in results.items()],
        "",
        f"MLflow run: {url}",
        "",
    ]
    text = "\n".join(lines)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "summary.md").write_text(text)
    return text


def run_all(cfg: Config) -> int:
    results = {}
    with stage_run(cfg, "pipeline") as parent:
        for name, stage in STAGES.items():
            print(f"\n==> {name}", flush=True)
            results[name] = stage(cfg)
            print(f"    {results[name]['summary']}", flush=True)
    print("\n" + write_summary(cfg, results, run_url(parent)))
    if not results["evaluate"]["gate_passed"]:
        print("Quality gate FAILED: the model was not registered.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("stage", choices=["all", *STAGES, "model-name", "ui"])
    parser.add_argument("--dataset", choices=DATASETS, help="override the dataset set in team.yaml")
    parser.add_argument("--endpoint", help="predict: call this model API instead of loading the model from the registry")
    args = parser.parse_args(argv)
    cfg = load_config(dataset=args.dataset)

    if args.stage == "model-name":
        print(cfg.model_name)
        return 0
    if args.stage == "ui":
        print(ui_url())
        return 0

    wait_for_server()
    if args.stage == "all":
        return run_all(cfg)
    result = predict.run(cfg, endpoint=args.endpoint) if args.stage == "predict" else STAGES[args.stage](cfg)
    print(result["summary"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
