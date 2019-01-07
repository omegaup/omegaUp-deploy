import json
import logging
import os
import sys
import subprocess
from problems import problems

import compiler

def enumerateFullPath(path):
    if os.path.exists(path):
        return [os.path.join(path, f) for f in os.listdir(path)]
    else:
        return []

logger = logging.getLogger(__name__)

logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

force = '--force' in sys.argv

for p in problems():
    path = p['path']
    title = p['title']

    logger.info('Generating outputs for problem: {}'.format(title))

    if p.get('disabled', False):
        logger.warn('Problem disabled.'.format(title))
        continue

    with open(os.path.join(path, 'settings.json'), 'r') as pc:
        pConfig = json.loads(pc.read())

    if 'cases' in pConfig:
        testplan = os.path.join(path, 'testplan')

        logger.info('Generating testplan from settings.json.')

        if os.path.isfile(testplan):
            logger.error('testplan cannot exist when settings.json has cases!')
            sys.exit(1)

        with open(testplan, 'w') as tp:
            for group in pConfig['cases']:
                for case in group['cases']:
                    tp.write("{} {}\n".format(
                        case['name'], case['weight']
                    ))

    generators = [x for x in os.listdir(path) if x.startswith('generator')]

    if not generators:
        logger.warn('No generator found! Skipping.')
        # TODO: check .ins and .outs match
        continue
    if len(generators) != 1:
        logger.error('Found more than one generator!')
        sys.exit(1)

    genPath = os.path.join(path, generators[0])

    with compiler.compile(genPath) as generator:
        casesPath = os.path.join(path, 'cases')
        examplesPath = os.path.join(path, 'examples')

        languages = pConfig['misc']['languages'] 

        # TODO: if karel, enforce examples

        if languages != 'none':
            ins = [f
                   for f in enumerateFullPath(cpath)
                   if f.endswith('.in')
                   for cpath in [casesPath, examplesPath]]
            outs = []

            if not ins:
                raise Exception('No test cases found!')

            for f_in in ins:
                f_out = f_in[:-3] + '.out'

                if not force and os.path.isfile(f_out):
                    raise Exception(
                        ".outs can't be present when generator.$lang$ exists: " + f_out)

                with open(f_in, 'r') as in_file, open(f_out, 'w') as out_file:
                    logger.info('Generating output for: ' + f_in)

                    ret = subprocess.call(generator,
                                          stdin=in_file,
                                          stdout=out_file,
                                          timeout=5)

                    if ret != 0:
                        raise Exception("Model solution RTE!")

                if languages == 'karel':
                    f_png = f_in[:-3] + '.png'

                    logger.info('Generating png: ' + f_png)
                    command = ['kareljs', 'draw', "--output", f_png]

                    with open(f_in, 'r') as in_file:
                        ret = subprocess.call(command,
                                              stdin=in_file,
                                              timeout=5)

                    if ret != 0:
                        raise Exception("png creation failure!")

    print('Success generating outputs for {}'.format(title))
