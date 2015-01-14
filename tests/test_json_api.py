import unittest
import requests
import os

HOST = os.environ.get('NCPAHOST', 'localhost')
PORT = int(os.environ.get('NCPAPORT', '5693'))


def make_api_request(address, arguments):
    url = "https://{0}:{1}/{2}".format(HOST, PORT, address)
    return requests.get(url, verify=False, params=arguments).json()


class TestBuiltInCommands(unittest.TestCase):
    tmpl = 'api/%s/%s'

    def get_token(self):
        return {'token': 'mytoken'}

    def test_cpu_api(self):
        key = 'cpu'
        testables = [
            {'key': 'idle',
             'validator': int,
             'unit': 'ms'},
            {'key': 'percent',
             'validator': int,
             'unit': '%'},
            {'key': 'system',
             'validator': int,
             'unit': 'ms'},
            {'key': 'count',
             'validator': int,
             'unit': 'c'},
            {'key': 'user',
             'validator': int,
             'unit': 'ms'}]
        for t in testables:
            arguments = self.get_token()
            target = self.tmpl % (key, t['key'])
            r = make_api_request(target, arguments)
            lat = r['value'][t['key']]
            for x in lat[0]:
                t['validator'](x)
            self.assertEquals(lat[1], t['unit'])

    def test_logical_disk_api(self):
        arguments = self.get_token()
        key = 'disk'
        target = self.tmpl % (key, 'logical')
        logical_disks = make_api_request(target, arguments)
        l = logical_disks['value']['logical']
        logical_keys = [
            {'key': 'device_name',
             'validator': str,
             'unit': 'name'},
            {'key': 'free',
             'validator': int,
             'unit': 'b'},
            {'key': 'total_size',
             'validator': int,
             'unit': 'b'},
            {'key': 'used',
             'validator': int,
             'unit': 'b'},
            {'key': 'used_percent',
             'validator': int,
             'unit': '%'}]
        # Get all entries in this particular computers enumerated disks
        for disk in l:
            # Iterate through our testing dictionary and make sure that it
            # validates properly.
            for k in logical_keys:
                target = self.tmpl % (key, os.path.join('logical', disk,
                                                        k['key']))
                r = make_api_request(target, arguments)
                lat = r['value'][k['key']]
                try:
                    for x in lat[0]:
                        k['validator'](x)
                except:
                    k['validator'](lat[0])
                self.assertEquals(lat[1], k['unit'])

    def test_physical_disk_api(self):
        arguments = self.get_token()
        key = 'disk'
        target = self.tmpl % (key, 'physical')
        physical_disks = make_api_request(target, arguments)
        p = physical_disks['value']['physical']
        physical_keys = [
            {'key': 'read_bytes',
             'validator': str,
             'unit': 'b'},
            {'key': 'read_count',
             'validator': int,
             'unit': 'c'},
            {'key': 'read_time',
             'validator': int,
             'unit': 'ms'},
            {'key': 'write_bytes',
             'validator': int,
             'unit': 'b'},
            {'key': 'write_count',
             'validator': int,
             'unit': 'c'},
            {'key': 'write_time',
             'validator': int,
             'unit': 'ms'}]
        # Get all entries in this particular computers enumerated disks
        for disk in p:
            # Iterate through our testing dictionary and make sure that it
            # validates properly.
            for k in physical_keys:
                target = self.tmpl % (key, os.path.join('physical', disk,
                                                        k['key']))
                r = make_api_request(target, arguments)
                lat = r['value'][k['key']]
                try:
                    for x in lat[0]:
                        k['validator'](x)
                except:
                    k['validator'](lat[0])
                self.assertEquals(lat[1], k['unit'])

