from datetime import date, datetime
import unittest
import time
import six

from analytics.version import VERSION
from analytics.client import Client


class TestClient(unittest.TestCase):

    def fail(self, e, batch):
        """Mark the failure handler"""
        self.failed = True

    def setUp(self):
        self.failed = False
        self.client = Client('testsecret', on_error=self.fail)

    def test_requires_write_key(self):
        self.assertRaises(AssertionError, Client)

    def test_empty_flush(self):
        self.client.flush()

    def test_basic_track(self):
        client = self.client
        success, msg = client.track('userId', 'python test event')
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['event'], 'python test event')
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['properties'], {})
        self.assertEqual(msg['type'], 'track')

    def test_stringifies_user_id(self):
        # A large number that loses precision in node:
        # node -e "console.log(157963456373623802 + 1)" > 157963456373623800
        client = self.client
        success, msg = client.track(user_id = 157963456373623802, event = 'python test event')
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['userId'], '157963456373623802')
        self.assertEqual(msg['anonymousId'], None)

    def test_stringifies_anonymous_id(self):
        # A large number that loses precision in node:
        # node -e "console.log(157963456373623803 + 1)" > 157963456373623800
        client = self.client
        success, msg = client.track(anonymous_id = 157963456373623803, event = 'python test event')
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['userId'], None)
        self.assertEqual(msg['anonymousId'], '157963456373623803')

    def test_advanced_track(self):
        client = self.client
        success, msg = client.track(
            'userId', 'python test event', { 'property': 'value' },
            { 'ip': '192.168.0.1' }, datetime(2014, 9, 3), 'anonymousId',
            { 'Amplitude': True })

        self.assertTrue(success)

        self.assertEqual(msg['timestamp'], '2014-09-03T00:00:00+00:00')
        self.assertEqual(msg['properties'], { 'property': 'value' })
        self.assertEqual(msg['integrations'], { 'Amplitude': True })
        self.assertEqual(msg['context']['ip'], '192.168.0.1')
        self.assertEqual(msg['event'], 'python test event')
        self.assertEqual(msg['anonymousId'], 'anonymousId')
        self.assertEqual(msg['context']['library'], {
            'name': 'analytics-python',
            'version': VERSION
        })
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'track')

    def test_basic_identify(self):
        client = self.client
        success, msg = client.identify('userId', { 'trait': 'value' })
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['traits'], { 'trait': 'value' })
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'identify')

    def test_advanced_identify(self):
        client = self.client
        success, msg = client.identify(
            'userId', { 'trait': 'value' }, { 'ip': '192.168.0.1' },
            datetime(2014, 9, 3), 'anonymousId', { 'Amplitude': True })

        self.assertTrue(success)

        self.assertEqual(msg['timestamp'], '2014-09-03T00:00:00+00:00')
        self.assertEqual(msg['integrations'], { 'Amplitude': True })
        self.assertEqual(msg['context']['ip'], '192.168.0.1')
        self.assertEqual(msg['traits'], { 'trait': 'value' })
        self.assertEqual(msg['anonymousId'], 'anonymousId')
        self.assertEqual(msg['context']['library'], {
            'name': 'analytics-python',
            'version': VERSION
        })
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'identify')

    def test_basic_group(self):
        client = self.client
        success, msg = client.group('userId', 'groupId')
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['groupId'], 'groupId')
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'group')

    def test_advanced_group(self):
        client = self.client
        success, msg = client.group(
            'userId', 'groupId', { 'trait': 'value' }, { 'ip': '192.168.0.1' },
            datetime(2014, 9, 3), 'anonymousId', { 'Amplitude': True })

        self.assertTrue(success)

        self.assertEqual(msg['timestamp'], '2014-09-03T00:00:00+00:00')
        self.assertEqual(msg['integrations'], { 'Amplitude': True })
        self.assertEqual(msg['context']['ip'], '192.168.0.1')
        self.assertEqual(msg['traits'], { 'trait': 'value' })
        self.assertEqual(msg['anonymousId'], 'anonymousId')
        self.assertEqual(msg['context']['library'], {
            'name': 'analytics-python',
            'version': VERSION
        })
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'group')

    def test_basic_alias(self):
        client = self.client
        success, msg = client.alias('previousId', 'userId')
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)
        self.assertEqual(msg['previousId'], 'previousId')
        self.assertEqual(msg['userId'], 'userId')

    def test_basic_page(self):
        client = self.client
        success, msg = client.page('userId', name='name')
        self.assertFalse(self.failed)
        client.flush()
        self.assertTrue(success)
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'page')
        self.assertEqual(msg['name'], 'name')

    def test_advanced_page(self):
        client = self.client
        success, msg = client.page(
            'userId', 'category', 'name', { 'property': 'value' },
            { 'ip': '192.168.0.1' }, datetime(2014, 9, 3), 'anonymousId',
            { 'Amplitude': True })

        self.assertTrue(success)

        self.assertEqual(msg['timestamp'], '2014-09-03T00:00:00+00:00')
        self.assertEqual(msg['integrations'], { 'Amplitude': True })
        self.assertEqual(msg['context']['ip'], '192.168.0.1')
        self.assertEqual(msg['properties'], { 'property': 'value' })
        self.assertEqual(msg['anonymousId'], 'anonymousId')
        self.assertEqual(msg['context']['library'], {
            'name': 'analytics-python',
            'version': VERSION
        })
        self.assertEqual(msg['category'], 'category')
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'page')
        self.assertEqual(msg['name'], 'name')

    def test_basic_screen(self):
        client = self.client
        success, msg = client.screen('userId', name='name')
        client.flush()
        self.assertTrue(success)
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'screen')
        self.assertEqual(msg['name'], 'name')

    def test_advanced_screen(self):
        client = self.client
        success, msg = client.screen(
            'userId', 'category', 'name', { 'property': 'value' },
            { 'ip': '192.168.0.1' }, datetime(2014, 9, 3), 'anonymousId',
            { 'Amplitude': True })

        self.assertTrue(success)

        self.assertEqual(msg['timestamp'], '2014-09-03T00:00:00+00:00')
        self.assertEqual(msg['integrations'], { 'Amplitude': True })
        self.assertEqual(msg['context']['ip'], '192.168.0.1')
        self.assertEqual(msg['properties'], { 'property': 'value' })
        self.assertEqual(msg['anonymousId'], 'anonymousId')
        self.assertEqual(msg['context']['library'], {
            'name': 'analytics-python',
            'version': VERSION
        })
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['category'], 'category')
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'screen')
        self.assertEqual(msg['name'], 'name')

    def test_flush(self):
        client = self.client
        # set up the consumer with more requests than a single batch will allow
        for i in range(1000):
            success, msg = client.identify('userId', { 'trait': 'value' })
        # We can't reliably assert that the queue is non-empty here; that's
        # a race condition. We do our best to load it up though.
        client.flush()
        # Make sure that the client queue is empty after flushing
        self.assertTrue(client.queue.empty())

    def test_overflow(self):
        client = Client('testsecret', max_queue_size=1)
        # Ensure consumer thread is no longer uploading
        client.join()

        for i in range(10):
          client.identify('userId')

        success, msg = client.identify('userId')
        # Make sure we are informed that the queue is at capacity
        self.assertFalse(success)

    def test_success_on_invalid_write_key(self):
        client = Client('bad_key', on_error=self.fail)
        client.track('userId', 'event')
        client.flush()
        self.assertFalse(self.failed)

    def test_unicode(self):
        Client(six.u('unicode_key'))

    def test_numeric_user_id(self):
        self.client.track(1234, 'python event')
        self.client.flush()
        self.assertFalse(self.failed)

    def test_debug(self):
        Client('bad_key', debug=True)

    def test_identify_with_date_object(self):
        client = self.client
        success, msg = client.identify(
            'userId',
            {
                'birthdate': date(1981, 2, 2),
            },
        )
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['traits'], {'birthdate': date(1981, 2, 2)})
