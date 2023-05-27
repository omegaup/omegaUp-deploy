import click
import os
import logging
import json

from .template import files
from src.problems import repositoryRoot
import src.utils as utils

@click.command()
@click.option("--root", default=repositoryRoot(), help="The root directory of the project.")
@click.option("--path", prompt=True, help="The directory name of the problem.")
@click.option("--title", prompt=True, default="<title>", help="The title of the problem.")
@click.option("--source", prompt=True, default="<source>", help="The source of the problem.")
def problem(
  root: str,
  path: str,
  title: str,
  source: str,
):
  config = utils.problems_json(root)
  
  # Check if problem already exists
  problem_paths = [problem['path'] for problem in config['problems']]
  if path in problem_paths:
    pass
    #raise click.ClickException(f"Problem {path} already exists.")
  # Check if directory already exists
  if os.path.exists(os.path.join(root, path)):
    raise click.ClickException(f"Directory {path} already exists.")
  
  logging.info(f"Creating problem {path}...")
  # Appending problem to problems.json
  config["problems"].append({
    "path": path,
  })
  # utils.save_problems_json(root, config)
  # Creating problem directory
  dirs = ["cases", "examples", "statements"]
  for dir in dirs:
    pass
    #os.makedirs(os.path.join(root, path, dir))
  # Creating template files
  d = {
    "title": title,
    "source": source,
  }
  for file in files:
    # Checking if file already exists
    if os.path.exists(os.path.join(root, path, file["path"])):
      raise click.ClickException(f"File {file['path']} already exists.")
    # Creating file
    with open(os.path.join(root, path, file["path"]), "w") as f:
      logging.info(f"Creating file {title}...")
      f.write(file["content"].format(**d))
