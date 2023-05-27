import os
import json


def problems_json(repositoryRoot: str):
    with open(os.path.join(repositoryRoot, 'problems.json'), 'r') as p:
        config = json.load(p)
    return config


def save_problems_json(repositoryRoot: str, config) -> None:
    """Save the problems.json file."""
    with open(os.path.join(repositoryRoot, 'problems.json'), 'w') as p:
        json.dump(config, p, indent=2)
