import click

from src.click.commands.new.problem import problem


@click.group()
def new() -> None:
    pass


new.add_command(problem)
