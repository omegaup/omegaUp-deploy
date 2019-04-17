import libkarel

import sys
import os
import traceback

from collections import deque

class TestFailure(Exception):
    pass

class KarelTest:
    filename = None

    def __init__(self):
        self.world = libkarel.KarelInput(sys.stdin.read())
        self.caseName = sys.argv[1]

    def reachableCells(self):
        s = (self.world.x, self.world.y)

        q = deque()
        q.append(s)

        v = set([s])

        def trypush(x, y):
            if (x, y) not in v:
                v.add((x, y))
                q.append((x, y))

        while q:
            x, y = q.popleft()
            w = self.world.paredes(x, y)

            if not w & libkarel.Direccion.NORTE:
                trypush(x, y + 1)
            if not w & libkarel.Direccion.SUR:
                trypush(x, y - 1)
            if not w & libkarel.Direccion.ESTE:
                trypush(x + 1, y)
            if not w & libkarel.Direccion.OESTE:
                trypush(x - 1, y)

        return v

    def worldBoundaries(self):
        x, y = zip(*self.reachableCells())
        return max(x), max(y)

    def assertTightWorldSize(self):
        x, y = self.worldBoundaries()
        self.assertEqual(self.world.w, x)
        self.assertEqual(self.world.h, y)

    def assertNoInnerWalls(self):
        cells = self.reachableCells()

        for x, y in cells:
            w = self.world.paredes(x, y)

            self.assertTrue((x, y + 1) not in cells or
                            (not w & libkarel.Direccion.NORTE))
            self.assertTrue((x, y - 1) not in cells or
                            (not w & libkarel.Direccion.SUR))
            self.assertTrue((x + 1, y) not in cells or
                            (not w & libkarel.Direccion.ESTE))
            self.assertTrue((x - 1, y) not in cells or
                            (not w & libkarel.Direccion.OESTE))

    def run(self):
        try:
            self.test()
        except:
            sys.stderr.write(traceback.format_exc())
            print(0)
        else:
            print(1)

    def assertTrue(self, p):
        if not p:
            raise TestFailure()

    def assertFalse(self, p):
        if p:
            raise TestFailure()

    def assertEqual(self, p, q):
        if p != q:
            raise TestFailure(
                'Equality failure!\nExpected: {}\nGot: {}'.format(q,p)
            )

    def assertNotEqual(self, p, q):
        if p == q:
            raise TestFailure(
                'Inequality failure!\nGot: {}'.format(p)
            )
