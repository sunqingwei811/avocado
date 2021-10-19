import os
import unittest

import avocado_robot
import pkg_resources

from avocado.core.resolver import ReferenceResolutionResult


def python_module_available(module_name):
    '''
    Checks if a given Python module is available

    :param module_name: the name of the module
    :type module_name: str
    :returns: if the Python module is available in the system
    :rtype: bool
    '''
    try:
        pkg_resources.require(module_name)
        return True
    except pkg_resources.DistributionNotFound:
        return False


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROBOT_AVOCADO = os.path.join(THIS_DIR, 'avocado.robot')


class Loader(unittest.TestCase):

    @unittest.skipUnless(python_module_available('robotframework'),
                         'robotframework python module missing')
    @unittest.skipUnless(python_module_available('avocado-framework-plugin-robot'),
                         'avocado-framework-plugin-robot python module missing')
    @unittest.skipUnless(os.path.isfile(ROBOT_AVOCADO),
                         'Robot test file not found at "%s"' % ROBOT_AVOCADO)
    def test_discover(self):
        loader = avocado_robot.RobotLoader(None, {})
        results = loader.discover(ROBOT_AVOCADO)
        self.assertEqual(len(results), 2)
        nosleep_klass, nosleep_params = results[0]
        self.assertIs(nosleep_klass, avocado_robot.RobotTest)
        self.assertEqual(nosleep_params['name'],
                         "%s:Avocado.NoSleep" % ROBOT_AVOCADO)
        sleep_klass, sleep_params = results[1]
        self.assertIs(sleep_klass, avocado_robot.RobotTest)
        self.assertEqual(sleep_params['name'],
                         "%s:Avocado.Sleep" % ROBOT_AVOCADO)


class Resolver(unittest.TestCase):
    @unittest.skipUnless(python_module_available('robotframework'),
                         'robotframework python module missing')
    @unittest.skipUnless(python_module_available('avocado-framework-plugin-robot'),
                         'avocado-framework-plugin-robot python module missing')
    @unittest.skipUnless(os.path.isfile(ROBOT_AVOCADO),
                         'Robot test file not found at "%s"' % ROBOT_AVOCADO)
    def test_resolver(self):
        res = avocado_robot.RobotResolver().resolve(ROBOT_AVOCADO)
        self.assertEqual(res.result, ReferenceResolutionResult.SUCCESS)
        self.assertEqual(len(res.resolutions), 2)
        nosleep = res.resolutions[0]
        self.assertEqual(nosleep.kind, 'robot')
        self.assertEqual(nosleep.uri,
                         os.path.join(THIS_DIR, 'avocado.robot:Avocado.NoSleep'))
        sleep = res.resolutions[1]
        self.assertEqual(nosleep.kind, 'robot')
        self.assertEqual(sleep.uri,
                         os.path.join(THIS_DIR, 'avocado.robot:Avocado.Sleep'))
