import logging
import os
import sys
import subprocess

class compile:
    def __init__(self, filename):
        self.filename = filename
        self.toRemove = []

    def __enter__(self):
        if self.filename.endswith('.kp') or self.filename.endswith('.kj'):
            return ['kareljs', 'run', self.filename]
        elif self.filename.endswith('.py'):
            return ['python3', self.filename]
        elif self.filename.endswith('.cpp'):
            binary = './solution'

            command = ["g++", "--std=gnu++11", "-O2", "-o", binary, self.filename]
            ret = subprocess.call(command,
                                  stdout=sys.stdout,
                                  stderr=sys.stderr,
                                  timeout=10)

            if ret != 0:
                raise Exception('Compilation error!')

            self.toRemove.append(binary)

            return [binary]
        else:
            raise Exception('Unknown extension: {}'.format(self.filename))

    def __exit__(self, exception_type, exception_value, traceback):
        for f in self.toRemove:
            os.remove(f)
