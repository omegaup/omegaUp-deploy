import sys
import traceback
import unittest

class CTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input = sys.stdin.read()
        self.caseName = sys.argv[1]

    def run(self, result=None):
        try:
            self.test()
        except:
            sys.stderr.write(traceback.format_exc())
            print(0)
        else:
            print(1)
