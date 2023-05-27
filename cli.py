#!python3
import click
import logging

from src.click.commands.new import new


@click.group()
def ofmi_cli():
    pass


def _main():
    logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    ofmi_cli.add_command(new)
    ofmi_cli()


if __name__ == '__main__':
    _main()
