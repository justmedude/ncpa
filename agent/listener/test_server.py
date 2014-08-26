__author__ = 'nscott'
import unittest
import ConfigParser
import json

import listener.server


def api_getter(f):

    def wrapped(api_url, api_args=None):
        if api_args is None:
            api_args = {}
        return f(api_url, data=api_args, follow_redirects=True)

    return wrapped


def unwrap_raw_val(response):
    return json.loads(response.data)['value']


class TestServerApi(unittest.TestCase):

    def setUp(self):
        self.config = ConfigParser.ConfigParser()
        self.config.optionxform = str
        self.config.add_section('api')
        self.config.set('api', 'community_string', 'mytoken')
        self.config.add_section('plugin directives')
        self.config.set('plugin directives', 'plugin_path', '/tmp')

        listener.server.__INTERNAL__ = True
        listener.server.listener.config['iconfig'] = self.config
        self.c = listener.server.listener.test_client()
        self.g = api_getter(self.c.post)

        base = self.g('/api/')
        root = json.loads(base.data)

        self.root = root['value']['root']


class TestBaselineItems(TestServerApi):

    def test_baseline_items(self):
        """
        Checking all root nodes for valid JSON response

        """
        for item in self.root:
            r = self.g('/api/' + item)
            j = json.loads(r.data)
            self.assertIn('value', j)

            value = j['value']
            self.assertNotIn('NodeDoesNotExist', value)


class CheckableNumerical(TestServerApi):
    """
    Class to be overriden when writing a checkable numeric check.

    """
    api_url = None

    def shortDescription(self):
        return "Testing {} for handling checks and arguments".format(self.api_url)

    def assert_standard(self, response):
        self.assertIn('returncode', response)
        self.assertIn('stdout', response)

    def bare_check(self):
        r = unwrap_raw_val(self.g(self.api_url, {'check': 1}))
        self.assert_standard(r)

    def delta_check(self):
        r = unwrap_raw_val(self.g(self.api_url, {'check': 1, 'delta': 1}))
        self.assert_standard(r)

    def units_check(self):
        normal = unwrap_raw_val(self.g(self.api_url, {'check': 1}))
        for u in ['M', 'K', 'G']:
            r = unwrap_raw_val(self.g(self.api_url, {'check': 1, 'units': u}))
            self.assert_standard(r)
            self.assertNotEqual(normal, r)

    def run_all(self):
        self.bare_check()
        self.delta_check()
        self.units_check()


class TestCpuPercent(CheckableNumerical):
    api_url = '/api/cpu/percent'

    def test_run_check(self):
        self.run_all()


class TestCpuCount(CheckableNumerical):
    api_url = '/api/cpu/count'

    def test_run_check(self):
        self.run_all()
