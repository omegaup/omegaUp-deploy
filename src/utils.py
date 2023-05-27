import os
import json
from typing import Any


def problems_json(repositoryRoot: str) -> Any:
    with open(os.path.join(repositoryRoot, 'problems.json'), 'r') as p:
        config = json.load(p)
    return config


def save_problems_json(repositoryRoot: str, config: Any) -> None:
    """Save the problems.json file."""
    with open(os.path.join(repositoryRoot, 'problems.json'), 'w') as p:
        json.dump(config, p, indent=2)
