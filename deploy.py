#!/usr/bin/env python3

from omegaUp import omegaUp
from problem import Problem

import os
import argparse
import subprocess
import sys
import logging

logging.basicConfig(
    format = '%(asctime)s: %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S',
    level = logging.INFO
)

env = os.environ

parser = argparse.ArgumentParser(description='Deploy a problem to omegaUp.')

parser.add_argument('-u', '--username', nargs = 1, default = env['OMEGAUPUSER'])
parser.add_argument('-p', '--password', nargs = 1, default = env['OMEGAUPPASS'])
parser.add_argument('--onlychanges', action = 'store_true')
parser.add_argument('path', nargs = 1)

args = parser.parse_args()

path = args.path[0]
problemPath, problemDir = os.path.split(path)

if args.onlychanges:
    commitRange = None

    if env.get('TRAVIS'):
        commitRange = env['TRAVIS_COMMIT_RANGE']
    elif env.get('CIRCLECI'):
        commitRange = env['CIRCLE_COMPARE_URL'].split('/')[6]

    git = subprocess.Popen(
        ["git", "diff", "--name-only", "--diff-filter=AMDR", commitRange],
        stdout = subprocess.PIPE,
        cwd = problemPath)

    grep = subprocess.Popen(["grep", problemDir], stdin = git.stdout, stdout = subprocess.PIPE)
    wc = subprocess.Popen(["wc", "-l"], stdin = grep.stdout, stdout = subprocess.PIPE)

    git.wait()
    grep.wait()
    wc.wait()

    changes = int(wc.stdout.read())

    if changes == 0:
        print("No changes.")
        sys.exit(0)

zipName = 'upload.zip'

problem = Problem(path)

if problem.disabled:
    print("Problem upload disabled.")
    sys.exit(0)

problem.prepareZip(zipName)

oUp = omegaUp(args.username, args.password)

oUp.login()

if env.get('TRAVIS'):
    commit = env['TRAVIS_COMMIT']
elif env.get('CIRCLECI'):
    commit = env['CIRCLE_SHA1']
else:
    commit = 'XXXXXX'

message = 'Deployed automatically from commit ' + commit
oUp.uploadProblem(problem, zipName, message)

os.remove(zipName)

print('Success!')
