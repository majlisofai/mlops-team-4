import pytest

from pipeline.config import DATASETS, load_config
from pipeline.ingest import download


@pytest.fixture(scope="session", params=DATASETS)
def cfg(request, tmp_path_factory):
    """A config per dataset, with the pinned source data downloaded once into a temporary work dir."""
    cfg = load_config(dataset=request.param)
    cfg.work_root = tmp_path_factory.mktemp("work")
    download(cfg, cfg.work_dir / "raw")
    return cfg
