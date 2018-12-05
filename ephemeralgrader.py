import os
import sys
import logging

from collections import defaultdict

import requests
import json
from requests_toolbelt.multipart import decoder

class InvalidProblemException(Exception):
    pass

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

class EphemeralGrader:
    endpoint = "https://omegaup.com/grader/ephemeral/run/new/"

    def judge(self, source, language, graderInput):
        payload = {
            "input": graderInput,
            "language": language,
            "source": source,
        }

        r = requests.post(
                self.endpoint,
                json=payload,
                timeout=65)

        multipart = decoder.MultipartDecoder.from_response(r)

        for part in multipart.parts:
                if b'details' in part.headers[b'Content-Disposition']:
                    return json.loads(part.text)

    def prepareInput(self, path, config):
        casesPath = os.path.join(path, 'cases')

        cases = {}

        testplan = os.path.join(path, 'testplan')

        if os.path.isfile(testplan):
            with open(testplan, 'r') as tp:
                caseWeights = {}
                for line in tp.readlines():
                    name, points = line.split()

                    if float(points) != int(points):
                        raise InvalidProblemException(
                            'Test case weights must be integers.'
                        )

                    caseWeights[name] = int(points)

            totalScore = sum(caseWeights.values())

            if totalScore != 100:
                logger.error('Total score: {}'.format(totalScore))
                raise InvalidProblemException(
                    'The total score for a problem must be 100.'
                )
            else:
                logger.info('Total score is 100 as expected.')
        else:
            caseWeights = defaultdict(lambda: 1)

        for case in os.listdir(casesPath):
            if not case.endswith('.in'):
                continue

            case = case[:-3]
            casePath = os.path.join(casesPath, case)
            fin = casePath + '.in'
            fout = casePath + '.out'

            name, _ = os.path.splitext(os.path.basename(fin))

            this_case = {"weight": caseWeights[name]}

            with open(fin, 'r') as f:
                this_case['in'] = f.read()

            with open(fout, 'r') as f:
                this_case['out'] = f.read()

            cases[case] = this_case

        limits = config['limits']

        limits['TimeLimit'] = '{}ms'.format(limits['TimeLimit'])

        validator = config['validator']

        if validator['name'] == 'custom':
            validators = [x for x in os.listdir(path) if x.startswith('validator')]

            if not validators:
                logger.warn('No validator found! Skipping.')
                sys.exit(1)
            if len(validators) != 1:
                logger.error('Found more than one validator!')
                sys.exit(1)

            validatorPath = os.path.join(path, validators[0])

            _, lang = os.path.splitext(validatorPath)
            lang = lang[1:]

            with open(validatorPath, 'r') as v:
                source = v.read()

            validator['custom_validator'] = {
                'source': source,
                'language': lang
            }

        interactive = None
        if 'interactive' in config:
            interactive = config['interactive']

            interactivePath = os.path.join(path, 'interactive')

            idlPath = os.path.join(
                interactivePath, interactive['module_name'] + '.idl'
            )

            with open(idlPath, 'r') as f:
                interactive['idl'] = f.read()

            mains = [x
                     for x in os.listdir(interactivePath)
                     if x.startswith('Main') and 'distrib' not in x]

            if not mains:
                logger.warn('No Main found!')
                sys.exit(1)
            if len(mains) != 1:
                logger.error('Found more than one Main!')
                sys.exit(1)

            mainPath = os.path.join(interactivePath, mains[0])

            _, lang = os.path.splitext(mainPath)
            interactive['language'] = lang[1:]

            with open(mainPath, 'r') as v:
                interactive['main_source'] = v.read()

        request = {
            "cases": cases,
            "limits": limits,
            "validator": validator
        }

        if interactive:
            request["interactive"] = interactive

        return request
