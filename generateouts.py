import argparse
import json
import logging
import os
import sys
import subprocess
import re

import compiler
import problems

def enumerateFullPath(path):
    if os.path.exists(path):
        return [os.path.join(path, f) for f in os.listdir(path)]
    else:
        return []

def _main() -> None:
    parser = argparse.ArgumentParser('Generate outputs')
    parser.add_argument(
        '--all',
        action='store_true',
        help='Consider all problems, instead of only those that have changed')
    parser.add_argument('--force',
                        action='store_true',
                        help='Force re-generating all outputs')
    args = parser.parse_args()

    env = os.environ

    logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    anyFailure = False

    rootDirectory = problems.repositoryRoot()

    for p in problems.problems(allProblems=args.all,
                               rootDirectory=rootDirectory):
        logging.info('Generating outputs for problem: %s', p.title)

        if p.disabled:
            logging.warning('Problem disabled.')
            continue

        pPath = os.path.join(rootDirectory, p.path)

        with open(os.path.join(pPath, 'settings.json'), 'r') as pc:
            pConfig = json.loads(pc.read())

        if 'cases' in pConfig:
            testplan = os.path.join(pPath, 'testplan')

            logging.info('Generating testplan from settings.json.')

            if os.path.isfile(testplan):
                logging.error('testplan cannot exist when settings.json has cases!')
                sys.exit(1)

            with open(testplan, 'w') as tp:
                for group in pConfig['cases']:
                    for case in group['cases']:
                        tp.write("{} {}\n".format(
                            case['name'], case['weight']
                        ))

        generators = [x for x in os.listdir(pPath) if x.startswith('generator')]

        if not generators:
            logging.warning('No generator found! Skipping.')
            # TODO: check .ins and .outs match
            continue
        if len(generators) != 1:
            logging.error('Found more than one generator!')
            sys.exit(1)

        genPath = os.path.join(pPath, generators[0])

        with compiler.compile(genPath) as generator:
            casesPath = os.path.join(pPath, 'cases')
            examplesPath = os.path.join(pPath, 'examples')
            statementsPath = os.path.join(pPath, 'statements')

            languages = pConfig['misc']['languages']

            # TODO: if karel, enforce examples

            if languages != 'none':
                ins = [f
                       for cpath in [casesPath, examplesPath, statementsPath]
                       for f in enumerateFullPath(cpath)
                       if f.endswith('.in')]
                outs = []

                if not ins:
                    raise Exception('No test cases found!')

                for f_in in ins:
                    f_out = f_in[:-3] + '.out'

                    if not args.force and os.path.isfile(f_out):
                        raise Exception(
                            ".outs can't be present when generator.$lang$ exists: " + f_out)

                    with open(f_in, 'r') as in_file, open(f_out, 'w') as out_file:
                        logging.info('Generating output for: ' + f_in)

                        ret = subprocess.call(generator,
                                              stdin=in_file,
                                              stdout=out_file,
                                              timeout=5)

                        if ret != 0:
                            raise Exception("Model solution RTE!")

                    if languages == 'karel':
                        logging.info('Generating pngs.')

                        def generate(command):
                            logging.info('Running command: ' + str(command))

                            with open(f_in, 'r') as in_file:
                                ret = subprocess.call(command,
                                                      stdin=in_file,
                                                      stderr=subprocess.DEVNULL,
                                                      timeout=10)

                            if ret != 0:
                                raise Exception("png creation failure!")

                        dimOpts = []
                        dimMatch = re.search('\.(\d*)x(\d*)\.in', f_in)
                        if dimMatch:
                            dimOpts = ['--height', dimMatch.group(1), '--width', dimMatch.group(2)]

                        generate(['kareljs', 'draw', "--output", f_in + '.png'] + dimOpts)
                        generate(['kareljs', 'draw', "--output", f_out + '.png', "--run", genPath] + dimOpts)

        print('Success generating outputs for {}'.format(p.title))

if __name__ == '__main__':
    _main()
