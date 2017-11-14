import yaml
import os
import subprocess
from zipfile import *

def enumerateFullPath(path):
        return [os.path.join(path, f) for f in os.listdir(path)]

class Problem:
    def __init__(self, path):
        config = open(os.path.join(path, 'config.yaml'), 'r').read()

        self.path = path
        self.config = yaml.load(config)
        self.disabled = self.config.get('disabled', False)

    def prepareZip(self, zipPath):
        ins = [f for f in enumerateFullPath(os.path.join(self.path, 'cases')) if f.endswith('.in')]
        outs = []

        if self.config['generate-output']:
            subprocess.call(["g++", "-o", "solution", os.path.join(self.path, self.config['solution'])])

            for f_in in ins:
                f_out = f_in[:-3] + '.out'

                with open(f_in, 'r') as in_file, open(f_out, 'w') as out_file:
                    sol = subprocess.call('./solution',
                                          stdin = in_file,
                                          stdout = out_file,
                                          timeout = self.config.get('timeout', 1))

                outs.append(f_out)

            os.remove('solution')
        else:
            outs = [f for f in enumerateFullPath(os.path.join(self.path, 'cases')) if f.endswith('.out')]

        missing_outs = [i for i in ins if i[:-3] + '.out' not in outs]

        if missing_outs:
            raise Exception(missing_outs)

        with ZipFile(zipPath, 'w', compression = ZIP_DEFLATED) as archive:
            archive.write(os.path.join(self.path, 'statements/es.markdown'), 'statements/es.markdown')

            for case in ins + outs:
                _, name = os.path.split(case)
                archive.write(case, os.path.join('cases', name))
