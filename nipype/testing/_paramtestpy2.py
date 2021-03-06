# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Implementation of the parametric test support for Python 2.x
"""
#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# Stdlib
import unittest
from compiler.consts import CO_GENERATOR

#-----------------------------------------------------------------------------
# Classes and functions
#-----------------------------------------------------------------------------

def isgenerator(func):
    try:
        return func.func_code.co_flags & CO_GENERATOR != 0
    except AttributeError:
        return False

class ParametricTestCase(unittest.TestCase):
    """Write parametric tests in normal unittest testcase form.

    Limitations: the last iteration misses printing out a newline when running
    in verbose mode.
    """
    def run_parametric(self, result, testMethod):
        # But if we have a test generator, we iterate it ourselves
        testgen = testMethod()
        while True:
            try:
                # Initialize test
                result.startTest(self)

                # SetUp
                try:
                    self.setUp()
                except KeyboardInterrupt:
                    raise
                except:
                    result.addError(self, self._exc_info())
                    return
                # Test execution
                ok = False
                try:
                    testgen.next()
                    ok = True
                except StopIteration:
                    # We stop the loop
                    break
                except self.failureException:
                    result.addFailure(self, self._exc_info())
                except KeyboardInterrupt:
                    raise
                except:
                    result.addError(self, self._exc_info())
                # TearDown
                try:
                    self.tearDown()
                except KeyboardInterrupt:
                    raise
                except:
                    result.addError(self, self._exc_info())
                    ok = False
                if ok: result.addSuccess(self)

            finally:
                result.stopTest(self)

    def run(self, result=None):
        if result is None:
            result = self.defaultTestResult()
        testMethod = getattr(self, self._testMethodName)
        # For normal tests, we just call the base class and return that
        if isgenerator(testMethod):
            return self.run_parametric(result, testMethod)
        else:
            return super(ParametricTestCase, self).run(result)


def parametric(func):
    """Decorator to make a simple function into a normal test via unittest."""

    class Tester(ParametricTestCase):
        test = staticmethod(func)

    Tester.__name__ = func.__name__

    return Tester
