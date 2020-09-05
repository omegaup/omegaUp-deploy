import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import textwrap

import problems

def _getContainerName(ci: bool) -> str:
    """Ensures the container is present in the expected version."""
    if ci:
        # Since this is running on GitHub, downloading the image from the
        # GitHub container registry is significantly faster.
        containerName = 'docker.pkg.github.com/omegaup/quark/omegaup-runner-ci'
    else:
        # This does not require authentication.
        containerName = 'omegaup/runner-ci'

    taggedContainerName = f'{containerName}:v1.2.4'
    if not subprocess.check_output(
        ['docker', 'image', 'ls', '-q', taggedContainerName],
            universal_newlines=True).strip():
        logging.info('Downloading Docker image %s...', taggedContainerName)
        subprocess.check_call(['docker', 'pull', taggedContainerName])
    return taggedContainerName


def _main() -> None:
    rootDirectory = problems.repositoryRoot()

    parser = argparse.ArgumentParser('Run tests')
    parser.add_argument('--ci',
                        action='store_true',
                        help='Signal that this is being run from the CI.')
    parser.add_argument(
        '--all',
        action='store_true',
        help='Consider all problems, instead of only those that have changed')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Verbose logging')
    parser.add_argument('--results-directory',
                        default=os.path.join(rootDirectory, 'results'),
                        help='Directory to store the results of the runs')
    parser.add_argument('--only-pull-image',
                        action='store_true',
                        help='Don\'t run tests: only download the Docker container')
    args = parser.parse_args()

    env = os.environ

    logging.basicConfig(format='%(asctime)s: %(message)s',
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    if args.only_pull_image:
        _getContainerName()
        sys.exit(0)

    anyFailure = False

    if os.path.isdir(args.results_directory):
        shutil.rmtree(args.results_directory)
    os.makedirs(args.results_directory)

    for p in problems.problems(allProblems=args.all,
                               rootDirectory=rootDirectory):
        if p.disabled:
            logging.warn('Problem %s disabled. Skipping.', p.title)
            continue

        logging.info('Testing problem: %s...', p.title)

        problemResultsDirectory = os.path.join(args.results_directory, p.path)
        os.makedirs(problemResultsDirectory)
        # The results are written with the container's UID, which does not
        # necessarily match the caller's UID. To avoid that problem, we create
        # the results directory with very lax permissions so that the container
        # can write it.
        os.chmod(problemResultsDirectory, 0o777)
        with open(os.path.join(problemResultsDirectory, 'ci.log'), 'w') as f:
            pass
        # Also make the ci log's permissions very lax.
        os.chmod(os.path.join(problemResultsDirectory, 'ci.log'), 0o666)

        processResult = subprocess.run([
            'docker',
            'run',
            '--rm',
            '--volume',
            f'{rootDirectory}:/src',
            _getContainerName(args.ci),
            '-oneshot=ci',
            '-input',
            p.path,
            '-results',
            os.path.relpath(problemResultsDirectory, rootDirectory),
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

        # The CI might have written a log, but the stderr contents have a few
        # more things in it.
        with open(os.path.join(problemResultsDirectory, 'ci.log'), 'w') as f:
            f.write(processResult.stderr)

        report = json.loads(processResult.stdout)

        if report['state'] != 'passed':
            anyFailure = True

        if report['state'] == 'skipped':
            logging.error(
                'Skipped. (tests/tests.json, settings.json, or testplan are probably missing or invalid.)'
            )
            continue

        for testResult in report.get('tests', []):
            if testResult['type'] == 'solutions':
                expected = dict(testResult['solution'])
                del (expected['filename'])
                if not expected:
                    # If there are no constraints, by default expect the run to be accepted.
                    expected['verdict'] = 'AC'
                logsDirectory = os.path.join(problemResultsDirectory,
                                             str(testResult['index']))
            else:
                expected = {'verdict': 'AC'}
                logsDirectory = os.path.join(problemResultsDirectory,
                                             str(testResult['index']),
                                             'validator')
            got = {
                'verdict': testResult.get('result', {}).get('verdict'),
                'score': testResult.get('result', {}).get('score'),
            }

            logger.info(f'    {testResult["type"]:10} | '
                        f'{testResult["filename"][:40]:40} | '
                        f'{testResult["state"]:8} | '
                        f'expected={expected} got={got} | '
                        f'logs at {os.path.relpath(logsDirectory, rootDirectory)}')
            
            if testResult['state'] != 'passed':
                failedCases = set(c['name'] for g in testResult['groups']
                                            for c in g['cases']
                                            if c['verdict'] != 'AC')

                if os.path.isdir(logsDirectory):
                    for stderrFilename in os.listdir(logsDirectory):
                        if not stderrFilename.endswith('.err'):
                            continue
                        if not os.path.splitext(stderrFilename)[0] in failedCases:
                            continue

                        logger.info(f'{stderrFilename}:')
                        with open(os.path.join(logsDirectory, stderrFilename),
                                  'r') as out:
                            logger.info(textwrap.indent(out.read(), '    '))
                else:
                    logging.warning('Logs directory %r not found.', logsDirectory)

        logger.info(f'Results for {p.title}: {report["state"]}')
        logger.info(f'    Full logs and report in {problemResultsDirectory}')

    if anyFailure:
        sys.exit(1)


if __name__ == '__main__':
    _main()
