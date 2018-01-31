import yaml
import os
import subprocess
import logging

from zipfile import *

def enumerateFullPath(path):
        return [os.path.join(path, f) for f in os.listdir(path)]

class Problem:
    def __init__(self, path):
        config = open(os.path.join(path, 'config.yaml'), 'r').read()

        self.path = path
        self.config = yaml.load(config)

        self.disabled = self.config.get('disabled', False)
        self.create = self.config.get('create', True)
        self.interactive = self.config.get('interactive', False)
        self.generateOutput = self.config.get('generate-output', False)

        self.admins = self.config.get('admins', None)
        self.adminGroups = self.config.get('admin-groups', None)

        self.params = self.config.get('params', {})
        self.languages = self.params['languages']

        if self.generateOutput:
            if self.interactive:
                raise Exception("Interactive and generate-output can't both be enabled")

            self.solution = self.config['solution']
            self.timeout = self.config['timeout']

        self.alias = self.config['alias']

    def prepareZip(self, zipPath):
        if self.languages != 'none':
            ins = [f for f in enumerateFullPath(os.path.join(self.path, 'cases')) if f.endswith('.in')]
            outs = []

            if not ins:
                raise Exception('No test cases found!')

            if self.generateOutput:
                solutionSource = os.path.abspath(os.path.join(self.path, self.solution))

                if self.languages != 'karel':
                    subprocess.call(["g++", "-O2", "-o", "solution", solutionSource])

                for f_in in ins:
                    f_out = f_in[:-3] + '.out'

                    if os.path.isfile(f_out):
                        raise Exception(".outs can't be present when generateOutput is enabled: " + f_out)

                    with open(f_in, 'r') as in_file, open(f_out, 'w') as out_file:
                        if self.languages == 'karel':
                            command = ['kareljs', 'run', solutionSource]
                        else:
                            command = './solution'

                        ret = subprocess.call(command,
                                              stdin = in_file,
                                              stdout = out_file,
                                              timeout = self.timeout)

                        if ret != 0:
                            raise Exception("Model solution RTE!")

                    outs.append(f_out)

                if self.languages != 'karel':
                    os.remove('solution')
            else:
                outs = [f for f in enumerateFullPath(os.path.join(self.path, 'cases')) if f.endswith('.out')]

            missing_outs = [i for i in ins if i[:-3] + '.out' not in outs]

            if missing_outs:
                raise Exception(missing_outs)
        else:
            ins = outs = []

        karelSample = os.path.abspath(os.path.join(self.path, 'examples', 'sample.in'))
        if self.languages == 'karel' and not os.path.isfile(karelSample):
            raise Exception("Karel problems need an example file at examples/sample.in.")

        with ZipFile(zipPath, 'w', compression = ZIP_DEFLATED) as archive:
            def addFile(path):
                archive.write(path, os.path.relpath(path, self.path))

            def recursiveAdd(directory):
                for (dirpath, dirnames, filenames) in os.walk(os.path.join(self.path, directory)):
                    for f in filenames:
                        addFile(os.path.join(dirpath, f))

            testplan = os.path.join(self.path, 'testplan')

            if os.path.isfile(testplan):
                print('Adding testplan.')
                addFile(testplan)

            recursiveAdd('statements')

            if self.languages == 'karel':
                recursiveAdd('examples')

            for case in ins + outs:
                _, name = os.path.split(case)
                archive.write(case, os.path.join('cases', name))

            if self.interactive:
                recursiveAdd('interactive')
