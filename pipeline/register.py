"""Stage 6 - register: put a model that passed the gate in the registry; promote it to @champion when it beats the current one."""

from __future__ import annotations

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from pipeline.config import Config
from pipeline.tracking import git_sha, stage_run


def current_champion(client: MlflowClient, name: str):
    try:
        return client.get_model_version_by_alias(name, "champion")
    except MlflowException:
        return None


def run(cfg: Config) -> dict:
    state = cfg.load_state()
    client = MlflowClient()

    with stage_run(cfg, "register"):
        if not state.get("gate_passed"):
            mlflow.set_tag("decision", "rejected")
            return {"decision": "rejected", "summary": "skipped: the model did not pass the quality gate"}

        accuracy = state["holdout_accuracy"]
        version = mlflow.register_model(
            state["model_uri"],
            cfg.model_name,
            tags={
                "holdout_accuracy": repr(accuracy),  # full precision: promotion compares against it
                "data_sha256": state.get("data_sha256", ""),
                "git_sha": git_sha(),
                "team": cfg.team_name,
                "model_type": cfg.team["model"]["type"],
            },
        )
        client.update_registered_model(
            cfg.model_name, description=f"{cfg.data['title']}: predicts `{cfg.target}`. Owner: {cfg.team_name}."
        )
        client.set_registered_model_alias(cfg.model_name, "challenger", version.version)

        champion = current_champion(client, cfg.model_name)
        champion_accuracy = float(champion.tags.get("holdout_accuracy", "-inf")) if champion else float("-inf")
        if accuracy > champion_accuracy:
            client.set_registered_model_alias(cfg.model_name, "champion", version.version)
            decision = "promoted"
            summary = f"`{cfg.model_name}` v{version.version} is the new @champion"
        else:
            decision = "challenger"
            summary = (
                f"`{cfg.model_name}` v{version.version} is @challenger; "
                f"v{champion.version} stays @champion ({champion_accuracy:.3f} >= {accuracy:.3f})"
            )

        mlflow.log_params({"registered_model": cfg.model_name, "registered_version": version.version})
        mlflow.set_tag("decision", decision)

    cfg.save_state(registered_version=version.version, decision=decision)
    return {"decision": decision, "version": version.version, "summary": summary}
