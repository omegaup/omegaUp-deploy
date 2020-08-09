import logging
import os
import sys
import subprocess
import json

def problems():
    logger = logging.getLogger(__name__)
    logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

    env = os.environ

    logger.info('Moving up one directory...')
    os.chdir('..')

    logger.info('Loading problems...')

    with open('problems.json', 'r') as p:
        config = json.loads(p.read())

    problems = config['problems']

    if '--all' in sys.argv:
        logger.info('Loading everything as requested.')
        return problems

    problems = []

    logger.info('Loading git diff.')

    if env.get('TRAVIS_COMMIT_RANGE'):
        commitRange = env['TRAVIS_COMMIT_RANGE']
    elif env.get('CIRCLE_COMPARE_URL'):
        commitRange = env['CIRCLE_COMPARE_URL'].split('/')[6]
    elif env.get('GITHUB_BASE_COMMIT'):
        commitRange = env['GITHUB_BASE_COMMIT'] + '..HEAD'
    else:
        commitRange = 'origin/master...HEAD'

    git = subprocess.Popen(
        ["git", "diff", "--name-only", "--diff-filter=AMDR", commitRange],
        stdout = subprocess.PIPE)

    git.wait()
    changes = str(git.stdout.read().decode('utf8'))

    for p in config['problems']:
        path = p['path']
        title = p['title']

        logger.info('Loading {}.'.format(title))

        if path in changes:
            problems.append(p)
        else:
            logger.info('No changes. Skipping.')

    return problems
