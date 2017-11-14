#!/usr/bin/env python3

from omegaUp import omegaUp
from problem import Problem
import os
import argparse

env = os.environ

parser = argparse.ArgumentParser(description='Deploy a problem to omegaUp.')

parser.add_argument('-u', '--username', nargs = 1, default = env['OMEGAUPUSER'])
parser.add_argument('-p', '--password', nargs = 1, default = env['OMEGAUPPASS'])
parser.add_argument('alias', nargs = 1)

args = parser.parse_args()

zipName = 'upload.zip'

problem = Problem(args.alias[0])
problem.prepareZip(zipName)

oUp = omegaUp(args.username, args.password)

oUp.login()

message = 'Deployed automatically from commit ' + env.get('TRAVIS_COMMIT', 'XXXXXX')
status = oUp.uploadProblem(problem, zipName, message)

print(status)

os.remove(zipName)
