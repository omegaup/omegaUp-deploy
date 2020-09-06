import logging
import os
import sys
import subprocess
import json

from typing import List, NamedTuple, NoReturn, Optional


class Problem(NamedTuple):
    """Represents a single problem."""
    path: str
    title: str
    disabled: bool


def repositoryRoot() -> str:
    """Returns the root directory of the project.

    If this is a submodule, it gets the root of the top-level working tree.
    """
    return subprocess.check_output([
        'git', 'rev-parse', '--show-superproject-working-tree',
        '--show-toplevel'
    ],
                                   universal_newlines=True).strip().split()[0]


def enumerateFullPath(path: str) -> List[str]:
    """Returns a list of full paths for the files in `path`."""
    if not os.path.exists(path):
        return []
    return [os.path.join(path, f) for f in os.listdir(path)]


def ci_error(message: str,
             *,
             filename: Optional[str] = None,
             line: Optional[int] = None,
             col: Optional[int] = None) -> None:
    """Show an error message, only on the CI."""
    location = []
    if filename is not None:
        location.append(f'file={filename}')
    if line is not None:
        location.append(f'line={line}')
    if col is not None:
        location.append(f'col={col}')
    print(
        f'::error {",".join(location)}::' +
        message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A'))


def error(message: str,
          *,
          filename: Optional[str] = None,
          line: Optional[int] = None,
          col: Optional[int] = None,
          ci: bool = False) -> None:
    """Show an error message."""
    if ci:
        ci_error(message, filename=filename, line=line, col=col)
    logging.error(message)


def fatal(message: str,
          *,
          filename: Optional[str] = None,
          line: Optional[int] = None,
          col: Optional[int] = None,
          ci: bool = False) -> NoReturn:
    """Show a fatal message and exit."""
    error(message, filename=filename, line=line, col=col, ci=ci)
    sys.exit(1)


def problems(allProblems: bool = False,
             rootDirectory: Optional[str] = None) -> List[Problem]:
    """Gets the list of problems that will be considered.

    If `allProblems` is passed, all the problems that are declared in
    `problems.json` will be returned. Otherwise, only those that have
    differences with `upstream/master`.
    """
    env = os.environ
    if rootDirectory is None:
        rootDirectory = repositoryRoot()

    logging.info('Loading problems...')

    with open(os.path.join(rootDirectory, 'problems.json'), 'r') as p:
        config = json.load(p)

    configProblems: List[Problem] = []
    for problem in config['problems']:
        configProblems.append(
            Problem(path=problem['path'],
                    title=problem['title'],
                    disabled=problem.get('disabled', False)))

    if allProblems:
        logging.info('Loading everything as requested.')
        return configProblems

    logging.info('Loading git diff.')

    if env.get('TRAVIS_COMMIT_RANGE'):
        commitRange = env['TRAVIS_COMMIT_RANGE']
    elif env.get('CIRCLE_COMPARE_URL'):
        commitRange = env['CIRCLE_COMPARE_URL'].split('/')[6]
    elif env.get('GITHUB_BASE_COMMIT'):
        commitRange = env['GITHUB_BASE_COMMIT'] + '...HEAD'
    else:
        commitRange = 'origin/master...HEAD'

    changes = subprocess.check_output(
        ['git', 'diff', '--name-only', '--diff-filter=AMDR', commitRange],
        cwd=rootDirectory,
        universal_newlines=True)

    problems: List[Problem] = []
    for problem in configProblems:
        logging.info('Loading %s.', problem.title)

        if problem.path not in changes:
            logging.info('No changes to %s. Skipping.', problem.title)
            continue
        problems.append(problem)

    return problems
