import subprocess
import os
import logging


def repositoryRoot() -> str:
    """Returns the root directory of the project.

    If this is a submodule, it gets the root of the top-level working tree.
    """
    return subprocess.check_output([
        'git', 'rev-parse', '--show-superproject-working-tree',
        '--show-toplevel'
    ],
                                   universal_newlines=True).strip().split()[0]


def gitDiff(rootDirectory: str) -> str:
    """Returns the git diff of the current commit."""
    env = os.environ
    logging.info('Loading git diff.')

    if env.get('TRAVIS_COMMIT_RANGE'):
        commitRange = env['TRAVIS_COMMIT_RANGE']
    elif env.get('CIRCLE_COMPARE_URL'):
        commitRange = env['CIRCLE_COMPARE_URL'].split('/')[6]
    elif env.get('GITHUB_BASE_COMMIT'):
        commitRange = env['GITHUB_BASE_COMMIT'] + '...HEAD'
    else:
        commitRange = 'origin/main...HEAD'

    return subprocess.check_output(
        ['git', 'diff', '--name-only', '--diff-filter=AMDR', commitRange],
        cwd=rootDirectory,
        universal_newlines=True)
