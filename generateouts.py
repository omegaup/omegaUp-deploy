#!/usr/bin/python3
import argparse
import concurrent.futures
import datetime
import json
import logging
import os
import re
import subprocess
import sys

from typing import List

import container
import problems


def _generateOutputs(p: problems.Problem, *, rootDirectory: str, force: bool,
                     ci: bool) -> bool:
    """Generate .out and .png files for the provided problem."""
    logging.info('%-30s: Generating outputs for problem', p.title)

    pPath = os.path.join(rootDirectory, p.path)
    pConfigPath = os.path.join(pPath, 'settings.json')

    with open(pConfigPath, 'r') as pc:
        pConfig = json.load(pc)

    if 'cases' in pConfig:
        testplan = os.path.join(pPath, 'testplan')

        logging.info('%-30s: Generating testplan from settings.json.', p.title)

        if os.path.isfile(testplan):
            problems.fatal(
                'testplan cannot exist when settings.json has cases!',
                filename=os.path.relpath(testplan, rootDirectory),
                ci=ci)

        with open(testplan, 'w') as tp:
            for group in pConfig['cases']:
                for case in group['cases']:
                    tp.write("{} {}\n".format(case['name'], case['weight']))

    languages = pConfig['misc']['languages']
    if languages == 'none':
        return True

    generators = [x for x in os.listdir(pPath) if x.startswith('generator')]

    if not generators:
        logging.warning('%-30s: No generator found! Skipping.', p.title)
        # TODO: check .ins and .outs match
        return True
    if len(generators) != 1:
        problems.fatal(f'Found more than one generator! {generators}',
                       filename=os.path.relpath(pConfigPath, rootDirectory),
                       ci=ci)

    genPath = os.path.join(pPath, generators[0])
    relativeGenPath = os.path.relpath(genPath, rootDirectory)

    anyProblemFailure = False

    # TODO: if karel, enforce examples
    with container.Compile(sourcePath=genPath, ci=ci) as c:
        inFilenames = [
            f for subdirectory in ('cases', 'examples', 'statements')
            for f in problems.enumerateFullPath(
                os.path.join(pPath, subdirectory)) if f.endswith('.in')
        ]

        if not inFilenames:
            problems.fatal(f'No test cases found for {p.title}!',
                           filename=os.path.relpath(pConfigPath,
                                                    rootDirectory),
                           ci=ci)

        for inFilename in inFilenames:
            relativeInFilename = os.path.relpath(inFilename, rootDirectory)
            outFilename = f'{os.path.splitext(inFilename)[0]}.out'
            relativeOutFilename = os.path.relpath(outFilename, rootDirectory)

            logging.debug('%-30s: Generating output for %s', p.title,
                          inFilename)

            if not force and os.path.isfile(outFilename):
                problems.fatal(
                    (f".outs can't be present when generator.$lang$ "
                     f"exists: {relativeOutFilename}"),
                    filename=relativeOutFilename,
                    ci=ci)

            try:
                c.run(inFilename,
                      outFilename,
                      timeout=datetime.timedelta(seconds=5))
            except subprocess.CalledProcessError as cpe:
                anyProblemFailure = True
                with open(outFilename, 'r') as f:
                    problems.error((f'{relativeGenPath} failed running '
                                    f'with {relativeInFilename}:\n'
                                    f'stdout:\n{f.read()}\n'
                                    f'stderr:\n{cpe.stderr.decode("utf-8")}'),
                                   filename=relativeGenPath,
                                   ci=ci)

        if languages == 'karel':
            logging.info('%-30s: Generating pngs for problem', p.title)

            for inFilename in inFilenames:
                logging.debug('%-30s: Generating .pngs for %s', p.title,
                              inFilename)
                dimMatch = re.search(r'\.(\d*)x(\d*)\.in', inFilename)
                if dimMatch:
                    dimOpts = [
                        '--height',
                        dimMatch.group(1), '--width',
                        dimMatch.group(2)
                    ]
                else:
                    dimOpts = []

                try:
                    c.run_command([
                        '/opt/nodejs/lib/node_modules/karel/cmd/kareljs',
                        'draw',
                        '--output=-',
                    ] + dimOpts,
                                  stdinPath=inFilename,
                                  stdoutPath=f'{inFilename}.png',
                                  timeout=datetime.timedelta(seconds=10))
                except subprocess.CalledProcessError as cpe:
                    anyProblemFailure = True
                    problems.error((f'failed generating '
                                    f'input .png for {relativeInFilename}:\n' +
                                    cpe.stderr.decode("utf-8")),
                                   filename=relativeInFilename,
                                   ci=ci)
                    continue

                try:
                    c.run_command([
                        '/opt/nodejs/lib/node_modules/karel/cmd/kareljs',
                        'draw',
                        '--output=-',
                        '--run',
                        os.path.join('/src', c.containerSourceFilename),
                    ] + dimOpts,
                                  stdinPath=inFilename,
                                  stdoutPath=f'{outFilename}.png',
                                  timeout=datetime.timedelta(seconds=10))
                except subprocess.CalledProcessError as cpe:
                    anyProblemFailure = True
                    problems.error(
                        (f'{relativeGenPath} failed generating '
                         f'output .png with {relativeInFilename}:\n' +
                         cpe.stderr.decode("utf-8")),
                        filename=relativeGenPath,
                        ci=ci)

    if anyProblemFailure:
        logging.warning('%-30s: Failed generating some outputs', p.title)
        return False

    logging.info('%-30s: Success generating outputs', p.title)
    return True


def _main() -> None:
    parser = argparse.ArgumentParser('Generate outputs')
    parser.add_argument(
        '--all',
        action='store_true',
        help='Consider all problems, instead of only those that have changed')
    parser.add_argument('--ci',
                        action='store_true',
                        help='Signal that this is being run from the CI.')
    parser.add_argument('--force',
                        action='store_true',
                        help='Force re-generating all outputs')
    parser.add_argument('--jobs',
                        '-j',
                        default=min(32, (os.cpu_count() or 2) + 4),
                        help='Number of threads to run concurrently')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Verbose logging')
    parser.add_argument('problem_paths',
                        metavar='PROBLEM',
                        type=str,
                        nargs='*')
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s: %(message)s',
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    rootDirectory = problems.repositoryRoot()

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.jobs) as executor:
        futures: List[concurrent.futures.Future[bool]] = []

        for p in problems.problems(allProblems=args.all,
                                   rootDirectory=rootDirectory,
                                   problemPaths=args.problem_paths):
            futures.append(
                executor.submit(_generateOutputs,
                                p,
                                rootDirectory=rootDirectory,
                                force=args.force,
                                ci=args.ci))

        if not all(future.result()
                   for future in concurrent.futures.as_completed(futures)):
            logging.error('Some outputs failed to generate')
            sys.exit(1)


if __name__ == '__main__':
    _main()
