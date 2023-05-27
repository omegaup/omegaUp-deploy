import click

from src.click.commands.new.problem import problem


@click.group()
def new():
  pass

new.add_command(problem)
