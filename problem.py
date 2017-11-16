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

        if self.generateOutput:
            if self.interactive:
                raise Exception("Interactive and generate-output can't both be enabled")

            self.solution = self.config['solution']
            self.timeout = self.config['timeout']

        self.alias = self.config['alias']

    def prepareZip(self, zipPath):
        ins = [f for f in enumerateFullPath(os.path.join(self.path, 'cases')) if f.endswith('.in')]
        outs = []

        if self.generateOutput:
            subprocess.call(["g++", "-o", "solution", os.path.join(self.path, self.solution)])

            for f_in in ins:
                f_out = f_in[:-3] + '.out'

                with open(f_in, 'r') as in_file, open(f_out, 'w') as out_file:
                    sol = subprocess.call('./solution',
                                          stdin = in_file,
                                          stdout = out_file,
                                          timeout = self.timeout)

                outs.append(f_out)

            os.remove('solution')
        else:
            outs = [f for f in enumerateFullPath(os.path.join(self.path, 'cases')) if f.endswith('.out')]

        missing_outs = [i for i in ins if i[:-3] + '.out' not in outs]

        if missing_outs:
            raise Exception(missing_outs)

        with ZipFile(zipPath, 'w', compression = ZIP_DEFLATED) as archive:
            def recursiveAdd(directory):
                for (dirpath, dirnames, filenames) in os.walk(os.path.join(self.path, directory)):
                    for f in filenames:
                        fullpath = os.path.join(dirpath, f)
                        archive.write(fullpath, os.path.relpath(fullpath, self.path))

            recursiveAdd('statements')

            for case in ins + outs:
                _, name = os.path.split(case)
                archive.write(case, os.path.join('cases', name))

            if self.interactive:
                recursiveAdd('interactive')
