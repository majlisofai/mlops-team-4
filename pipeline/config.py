"""Load team.yaml and the dataset config it points to."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ("f1", "spl")


@dataclass
class Config:
    team: dict
    data: dict
    root: Path = ROOT
    work_root: Path = field(default=ROOT / "work")

    @property
    def team_name(self) -> str:
        return self.team["team"]

    @property
    def dataset(self) -> str:
        return self.data["name"]

    @property
    def experiment(self) -> str:
        return f"{self.team_name}-{self.dataset}"

    @property
    def model_name(self) -> str:
        return f"{self.team_name}-{self.dataset}-model"

    @property
    def target(self) -> str:
        return self.data["target"]

    @property
    def numeric(self) -> list[str]:
        return self.data["features"]["numeric"]

    @property
    def categorical(self) -> list[str]:
        return self.data["features"]["categorical"]

    @property
    def features(self) -> list[str]:
        return self.numeric + self.categorical

    @property
    def work_dir(self) -> Path:
        return self.work_root / self.dataset

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    # Stages hand small facts to each other (model URI, gate result...) through work/<dataset>/state.json.
    def load_state(self) -> dict:
        path = self.work_dir / "state.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def save_state(self, **updates) -> None:
        state = self.load_state() | updates
        self.work_dir.mkdir(parents=True, exist_ok=True)
        (self.work_dir / "state.json").write_text(json.dumps(state, indent=2))


def load_config(team_file: str | Path | None = None, dataset: str | None = None) -> Config:
    team = yaml.safe_load(Path(team_file or ROOT / "team.yaml").read_text())
    name = dataset or os.environ.get("MLOPS_DATASET") or team["dataset"]
    if name not in DATASETS:
        raise ValueError(f"dataset must be one of {DATASETS}, got {name!r}")
    data = yaml.safe_load((ROOT / "configs" / f"{name}.yaml").read_text())
    return Config(team=team, data=data)
