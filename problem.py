import yaml
from zipfile import *

class Problem:
    def __init__(self, path):
        config = open(path + '/config.yaml', 'r').read()

        self.path = path
        self.config = yaml.load(config)

    def prepareZip(self, path):
        with ZipFile(path, 'w') as archive:
            archive.write(self.path + '/statements/es.markdown', 'statements/es.markdown')
