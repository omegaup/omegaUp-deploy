import json
import logging
import os
import sys
import subprocess
from problems import problems

import compiler
import ephemeralgrader as eg
from problems import problems

class TestCaseFailure(Exception):
    pass

logger = logging.getLogger(__name__)

logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

# shut up
logging.getLogger('urllib3').setLevel(logging.CRITICAL)


env = os.environ

if env.get('CIRCLE_BRANCH', None) == 'master':
    git = subprocess.Popen(
        ["git", "log", "-1", "--pretty=%B"],
        stdout = subprocess.PIPE)

    git.wait()

    if '#test-all' in str(git.stdout.read()):
        logger.info('Testing everything as requested.')
    else:
        logger.info('Not running tests on master.')
        sys.exit(0)


anyFailure = False

for p in problems():
    path = p['path']
    title = p['title']

    logger.info('Testing problem: {}'.format(title))

    if p.get('disabled', False):
        logger.warn('Problem disabled.'.format(title))
        continue

    with open(os.path.join(path, 'settings.json'), 'r') as pc:
        pConfig = json.loads(pc.read())


    testPath = os.path.join(path, 'tests')
    testConfigPath = os.path.join(testPath, 'tests.json')

    if not os.path.isfile(testConfigPath):
        logger.error('Couldn\'t find tests.json!')
        sys.exit(1)

    with open(testConfigPath, 'r') as tc:
        testConfig = json.loads(tc.read())

    if not 'inputs' in testConfig or 'filename' not in testConfig['inputs']:
        logger.error('Couldn\'t find input validator!')
        sys.exit(1)

    checkerPath = os.path.join(testPath, testConfig['inputs']['filename'])

    caseFailures = []
    solutionFailures = []

    with compiler.compile(checkerPath) as checker:
        # the last argument to the checker is the name of the test case.
        checker.append('casename')

        casesPath = os.path.join(path, 'cases')

        for case in os.listdir(casesPath):
            try:
                if not case.endswith('.in'):
                    continue

                logger.info('Testing {}'.format(case))

                fin = os.path.join(casesPath, case)
                fout = fin[:-3] + '.out'

                name, _ = os.path.splitext(os.path.basename(case))

                checker[-1] = name

                if not os.path.isfile(fout):
                    logger.error('Couldn\'t find {}'.format(fout))
                    sys.exit(1)

                if os.path.islink('data.in'):
                    os.remove('data.in')
                if os.path.islink('data.out'):
                    os.remove('data.out')

                os.symlink(fin, 'data.in')
                os.symlink(fout, 'data.out')

                try:
                    with open(fin, 'r') as contents:
                        score = subprocess.check_output(
                            checker,
                            stdin=contents,
                            stderr=sys.stderr,
                            timeout=5)
                        score = float(score)
                except TestCaseFailure:
                    logger.error('Checker error.')
                    score = 0.0

                if score != 1:
                    raise TestCaseFailure
            except TestCaseFailure:
                logger.warning('Test failed: {}'.format(case))
                caseFailures.append(case)
            finally:
                if os.path.islink('data.in'):
                    os.remove('data.in')
                if os.path.islink('data.out'):
                    os.remove('data.out')

    if testConfig['solutions']:
        logger.info('Preparing {} for ephemeral grader'.format(title))

        grader = eg.EphemeralGrader()

        try:
            graderInput = grader.prepareInput(path, pConfig)
        except eg.InvalidProblemException as e:
            print("Invalid problem format: {}".format(title))
            print(e)

            anyFailure = True

            continue

        for solution in testConfig['solutions']:
            try:
                name = solution['filename']
                logger.info('Grading solution {}'.format(name))

                solPath = os.path.join(path, 'tests', name)
                with open(solPath, 'r') as contents:
                    source = contents.read()

                if 'language' in solution:
                    language = solution['language']
                else:
                    language = os.path.splitext(name)[1][1:]

                response = grader.judge(source, language, graderInput)

		if 'compile_error' in response:
		    logger.error('Compilation error:\n' +
				 response['compile_error'])

		    raise TestCaseFailure

                required = 0
                score = int(round(response['contest_score']))

                if 'verdict' in solution:
                    required += 1

                    if solution['verdict'] != response['verdict']:
                        logger.warning(
                            'Verdict mismatch! Expected {}, got {}'.format(
                                solution['verdict'], response['verdict']
                            )
                        )

                        raise TestCaseFailure

                if 'score' in solution:
                    required += 1

                    if score != solution['score']:
                        logger.warning(
                            'Score mismatch! Expected {}, got {}'.format(
                                solution['score'], score
                            )
                        )

                        raise TestCaseFailure
                elif 'score_range' in solution:
                    required += 1
                    lower_bound = solution['score_range'][0]
                    upper_bound = solution['score_range'][1]

                    if score < lower_bound or score > upper_bound:
                        logger.warning(
                            'Score out of bounds! Expected [{}, {}], got {}'.format(
                                lower_bound, upper_bound, score
                            )
                        )

                        raise TestCaseFailure

                if required == 0:
                    logger.warn('A verdict or a score bound is required.')
                    raise TestCaseFailure

            except TestCaseFailure:
                logger.warning('Solution test failed: {}'.format(name))

                if response:
                    if 'groups' in response and response['groups']:
                        groupVerdictStr = "Groups:\n" + "\t".join([
                            "name", "score"
                        ]) + '\n'

                        caseVerdictStr = "Cases:\n" + "\t".join([
                            "name", "score", "verdict", "wall_time"
                        ]) + '\n'

                        for group in response['groups']:
                            groupVerdictStr += "\t".join([
                                group['group'],
                                str(group['contest_score'])
                            ]) + '\n'

                            for case in group['cases']:
                                caseVerdictStr += "\t".join([
                                    case['name'],
                                    str(case['contest_score']),
                                    case['verdict'],
                                    str(case['meta']['wall_time']),
                                ]) + '\n'

                        logger.warning('Detailed verdict:')
                        logger.warning(groupVerdictStr.strip())
                        logger.warning(caseVerdictStr.strip())
                    else:
                        logger.warning('Judge response error...')
                        logger.warning(response)

                solutionFailures.append(name)
    else:
        logger.warning('No solutions to be tested!')

    print('Results for {}'.format(title))

    if caseFailures:
        print('Failed test cases:')
        print(caseFailures)
        anyFailure = True

    if solutionFailures:
        print('Failed solutions:')
        print(solutionFailures)
        anyFailure = True

    if not caseFailures and not solutionFailures:
        print('OK!')

if anyFailure:
    sys.exit(1)
