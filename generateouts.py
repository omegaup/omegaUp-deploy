#!/usr/bin/python3
import argparse
import datetime
import json
import logging
import os
import re

import container
import problems


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
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Verbose logging')
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s: %(message)s',
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    rootDirectory = problems.repositoryRoot()

    for p in problems.problems(allProblems=args.all,
                               rootDirectory=rootDirectory):
        logging.info('Generating outputs for problem: %s', p.title)

        if p.disabled:
            logging.warning('Problem disabled.')
            continue

        pPath = os.path.join(rootDirectory, p.path)
        pConfigPath = os.path.join(pPath, 'settings.json')

        with open(pConfigPath, 'r') as pc:
            pConfig = json.load(pc)

        if 'cases' in pConfig:
            testplan = os.path.join(pPath, 'testplan')

            logging.info('Generating testplan from settings.json.')

            if os.path.isfile(testplan):
                problems.fatal(
                    'testplan cannot exist when settings.json has cases!',
                    filename=testplan,
                    ci=args.ci)

            with open(testplan, 'w') as tp:
                for group in pConfig['cases']:
                    for case in group['cases']:
                        tp.write("{} {}\n".format(case['name'],
                                                  case['weight']))

        languages = pConfig['misc']['languages']
        if languages == 'none':
            continue

        generators = [
            x for x in os.listdir(pPath) if x.startswith('generator')
        ]

        if not generators:
            logging.warning('No generator found! Skipping.')
            # TODO: check .ins and .outs match
            continue
        if len(generators) != 1:
            problems.fatal(f'Found more than one generator! {generators}',
                           filename=pConfigPath,
                           ci=args.ci)

        genPath = os.path.join(pPath, generators[0])

        # TODO: if karel, enforce examples
        with container.Compile(sourcePath=genPath, ci=args.ci) as c:
            inFilenames = [
                f for subdirectory in ('cases', 'examples', 'statements')
                for f in problems.enumerateFullPath(
                    os.path.join(pPath, subdirectory)) if f.endswith('.in')
            ]

            if not inFilenames:
                problems.fatal(f'No test cases found for {p.title}!',
                               filename=pConfigPath,
                               ci=args.ci)

            for inFilename in inFilenames:
                outFilename = f'{os.path.splitext(inFilename)[0]}.out'
                logging.debug('Generating output for %s', inFilename)

                if not args.force and os.path.isfile(outFilename):
                    problems.fatal(
                        f".outs can't be present when "
                        f"generator.$lang$ exists: {outFilename}",
                        filename=outFilename,
                        ci=args.ci)

                c.run(inFilename,
                      outFilename,
                      timeout=datetime.timedelta(seconds=5))

            if languages == 'karel':
                logging.info('Generating pngs for problem: %s', p.title)

                for inFilename in inFilenames:
                    logging.debug('Generating .pngs for %s', inFilename)
                    dimMatch = re.search(r'\.(\d*)x(\d*)\.in', inFilename)
                    if dimMatch:
                        dimOpts = [
                            '--height',
                            dimMatch.group(1), '--width',
                            dimMatch.group(2)
                        ]
                    else:
                        dimOpts = []

                    c.run_command([
                        '/opt/nodejs/lib/node_modules/karel/cmd/kareljs',
                        'draw',
                        '--output=-',
                    ] + dimOpts,
                                  stdinPath=inFilename,
                                  stdoutPath=f'{inFilename}.png',
                                  timeout=datetime.timedelta(seconds=10))
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

        logging.info('Success generating outputs for %s', p.title)


if __name__ == '__main__':
    _main()
