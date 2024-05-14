import logging
import os
import sys
import json

from typing import Any, List, Mapping, NamedTuple, NoReturn, Optional, Sequence

import repository


class Problem(NamedTuple):
    """Represents a single problem."""
    path: str
    title: str
    config: Mapping[str, Any]

    @staticmethod
    def load(problemPath: str, rootDirectory: str) -> 'Problem':
        """Load a single problem from the path."""
        with open(os.path.join(rootDirectory, problemPath,
                               'settings.json')) as f:
            problemConfig = json.load(f)

        return Problem(path=problemPath,
                       title=problemConfig['title'],
                       config=problemConfig)

    def shouldGenerateOutputs(self, *, rootDirectory: str) -> bool:
        """Returns whether the .out files should be generated for this problem.

        .out files are only generated if there is a .gitignore file that
        contains the line `**/*.out` in the problem directory.
        """
        gitignorePath = os.path.join(rootDirectory, self.path, '.gitignore')
        if not os.path.isfile(gitignorePath):
            return False
        with open(gitignorePath, 'r') as f:
            for line in f:
                if line.strip() == '**/*.out':
                    return True
        return False


def enumerateFullPath(path: str) -> List[str]:
    """Returns a list of full paths for the files in `path`."""
    if not os.path.exists(path):
        return []
    return [os.path.join(path, f) for f in os.listdir(path)]


def ci_message(kind: str,
               message: str,
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
        f'::{kind} {",".join(location)}::' +
        message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A'),
        file=sys.stderr,
        flush=True)


def error(message: str,
          *,
          filename: Optional[str] = None,
          line: Optional[int] = None,
          col: Optional[int] = None,
          ci: bool = False) -> None:
    """Show an error message."""
    if ci:
        ci_message('error', message, filename=filename, line=line, col=col)
    else:
        logging.error(message)


def warning(message: str,
            *,
            filename: Optional[str] = None,
            line: Optional[int] = None,
            col: Optional[int] = None,
            ci: bool = False) -> None:
    """Show an error message."""
    if ci:
        ci_message('warning', message, filename=filename, line=line, col=col)
    else:
        logging.warning(message)


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
             problemPaths: Sequence[str] = (),
             rootDirectory: Optional[str] = None) -> List[Problem]:
    """Gets the list of problems that will be considered.

    If `allProblems` is passed, all the problems that are declared in
    `problems.json` will be returned. Otherwise, only those that have
    differences with `upstream/main`.
    """
    if rootDirectory is None:
        rootDirectory = repository.repositoryRoot()

    logging.info('Loading problems...')

    if problemPaths:
        # Generate the Problem objects from just the path. The title is ignored
        # anyways, since it's read from the configuration file in the problem
        # directory for anything important.
        return [
            Problem.load(problemPath=problemPath, rootDirectory=rootDirectory)
            for problemPath in problemPaths
        ]

    with open(os.path.join(rootDirectory, 'problems.json'), 'r') as p:
        config = json.load(p)

    configProblems: List[Problem] = []
    for problem in config['problems']:
        if problem.get('disabled', False):
            logging.warning('Problem %s disabled. Skipping.', problem['title'])
            continue
        configProblems.append(
            Problem.load(problemPath=problem['path'],
                         rootDirectory=rootDirectory))

    if allProblems:
        logging.info('Loading everything as requested.')
        return configProblems

    changes = repository.gitDiff(rootDirectory)

    problems: List[Problem] = []
    for problem in configProblems:
        logging.info('Loading %s.', problem.title)

        if problem.path not in changes:
            logging.info('No changes to %s. Skipping.', problem.title)
            continue
        problems.append(problem)

    return problems
