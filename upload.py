import json
import logging
import os
import sys
import subprocess
from zipfile import *
from time import sleep

import compiler
from omegaUp import *
from problems import problems

def enumerateFullPath(path):
    return [os.path.join(path, f) for f in os.listdir(path)]

env = os.environ

logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

oUp = omegaUp(env['OMEGAUPUSER'], env['OMEGAUPPASS'])
oUp.login()

for p in problems():
    path = p['path']

    with open(os.path.join(path, 'settings.json'), 'r') as pc:
        pConfig = json.loads(pc.read())

    title = pConfig['title']
    languages = pConfig['misc']['languages']

    logging.info('Uploading problem: {}'.format(title))

    waitTime = 2
    logging.info('Sleeping for {} seconds.'.format(waitTime))
    sleep(waitTime)

    zipPath = 'upload.zip'

    with ZipFile(zipPath, 'w', compression=ZIP_DEFLATED) as archive:
        def addFile(f):
            logging.info('writing {}'.format(f))
            archive.write(f, os.path.relpath(f, path))

        def recursiveAdd(directory):
            for (dirpath, dirnames, filenames) in os.walk(os.path.join(path, directory)):
                for f in filenames:
                    addFile(os.path.join(dirpath, f))

        testplan = os.path.join(path, 'testplan')

        if os.path.isfile(testplan):
            logging.info('Adding testplan.')
            addFile(testplan)

        if pConfig['validator']['name'] == 'custom':
            validators = [x for x in os.listdir(path) if x.startswith('validator')]

            if not validators:
                raise Exception('Custom validator missing!')
            if len(validators) != 1:
                raise Exception('More than one validator found!')

            validator = os.path.join(path, validators[0])

            addFile(validator)

        recursiveAdd('statements')
        recursiveAdd('solutions')

        if languages == 'karel':
            recursiveAdd('examples')

        recursiveAdd('cases')

        if os.path.isdir(os.path.join(path, 'interactive')):
            recursiveAdd('interactive')

    if env.get('TRAVIS'):
        commit = env['TRAVIS_COMMIT']
    elif env.get('CIRCLECI'):
        commit = env['CIRCLE_SHA1']
    elif env.get('GITHUB_ACTIONS'):
        commit = env['GITHUB_SHA']
    else:
        commit = 'XXXXXX'

    canCreate = '--create' in sys.argv

    message = 'Deployed automatically from commit ' + commit
    oUp.uploadProblem(pConfig, canCreate, zipPath, message)

    os.remove(zipPath)

    print('Success uploading {}'.format(title))
