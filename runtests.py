import argparse
import json
import logging
import os
import sys
import subprocess

import problems


def _main() -> None:
    parser = argparse.ArgumentParser('Run tests')
    parser.add_argument('--ci',
                        action='store_true',
                        help='Signal that this is being run from the CI.')
    parser.add_argument(
        '--all',
        action='store_true',
        help='Consider all problems, instead of only those that have changed')
    args = parser.parse_args()

    env = os.environ

    logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    anyFailure = False

    rootDirectory = problems.repositoryRoot()

    if args.ci:
        # Since this is running on GitHub, downloading the image from the
        # GitHub container registry is significantly faster.
        containerName = 'docker.pkg.github.com/omegaup/quark/omegaup-runner-ci'
    else:
        # This does not require authentication.
        containerName = 'omegaup/runner-ci'

    for p in problems.problems(allProblems=args.all,
                               rootDirectory=rootDirectory):
        logging.info('Testing problem: %s...', p.title)

        if p.disabled:
            logging.warn('Problem %s disabled. Skipping.', p.title)
            continue

        resultsDirectory = os.path.join('results', p.path)
        processResult = subprocess.run([
            'docker',
            'run',
            '--rm',
            '--volume',
            f'{rootDirectory}:/src',
            f'{containerName}:v1.2.2',
            '-oneshot=ci',
            '-input',
            p.path,
            '-results',
            resultsDirectory,
        ],
                                       universal_newlines=True,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       cwd=rootDirectory)

        if processResult.returncode != 0:
            logging.error(f'Failed to run %s:\n%s', p.title,
                          processResult.stderr)
            anyFailure = True
            continue

        report = json.loads(processResult.stdout)
        print(f'Results for {p.title}: {report["state"]}')
        if report['state'] == 'passed':
            continue

        anyFailure = True
        for testResult in report['tests']:
            if testResult['type'] == 'solutions':
                expected = dict(testResult['solution'])
                del (expected['filename'])
                if not expected:
                    # If there are no constraints, by default expect the run to be accepted.
                    expected['verdict'] = 'AC'
            else:
                expected = {'verdict': 'AC'}
            got = {
                'verdict': testResult.get('result', {}).get('verdict'),
                'score': testResult.get('result', {}).get('score'),
            }
            print(f'    {testResult["type"]:10} | '
                  f'{testResult["filename"][:40]:40} | '
                  f'{testResult["state"]:8} | '
                  f'expected={expected} got={got}')
        print()
        print(f'    Full logs and report in {resultsDirectory}')

    if anyFailure:
        sys.exit(1)


if __name__ == '__main__':
    _main()
