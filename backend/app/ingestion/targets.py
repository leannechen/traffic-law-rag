from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

TARGETS_PATH = Path(__file__).with_name("targets.yaml")


class Target(BaseModel):
    pcode: str
    short_name: str
    priority: Literal["must", "should", "could"]


def load_targets(path: Path = TARGETS_PATH) -> list[Target]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Target(**item) for item in data["targets"]]
