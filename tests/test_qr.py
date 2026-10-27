import base64
import io
import unittest
from unittest.mock import patch

import qrcode
from jinja2 import Template
from PIL import Image
from qrcode.exceptions import DataOverflowError

from data.initial_config_types import WIREGUARD_TEMPLATE
from utils.qr import (
    BORDER, BOX_SIZE, EMPTY_MESSAGE, ERROR_CORRECTION, MAX_VERSION,
    TOO_LARGE_MESSAGE, prepare_qr,
)


class QRTests(unittest.TestCase):
    def test_smallest_fitting_version(self):
        text = 'a' * 200
        result = prepare_qr(text)
        self.assertTrue(result.available)
        self.assertLessEqual(result.version, MAX_VERSION)
        smaller = qrcode.QRCode(
            version=result.version - 1, error_correction=ERROR_CORRECTION
        )
        smaller.add_data(text)
        with self.assertRaises(DataOverflowError):
            smaller.make(fit=False)

    def test_small_payload_uses_version_one(self):
        self.assertEqual(prepare_qr('test').version, 1)

    def test_capacity_boundary(self):
        # Version 15-M can store 412 bytes in byte mode, but not 413.
        self.assertEqual(prepare_qr('a' * 412).version, MAX_VERSION)
        result = prepare_qr('a' * 413)
        self.assertFalse(result.available)
        self.assertEqual(result.reason, TOO_LARGE_MESSAGE)

    def test_utf8_capacity_is_not_character_count(self):
        self.assertTrue(prepare_qr('я' * 206).available)
        self.assertFalse(prepare_qr('я' * 207).available)
        self.assertTrue(prepare_qr('a' * 207).available)

    def test_encoding_modes_affect_capacity(self):
        self.assertTrue(prepare_qr('1' * 500).available)
        self.assertFalse(prepare_qr('a' * 500).available)

    def test_oversized_payload_never_uses_auto_fit_or_exceeds_limit(self):
        calls = []
        original_make = qrcode.QRCode.make

        def record_make(qr, fit=True):
            calls.append((qr.version, fit))
            return original_make(qr, fit=fit)

        with patch.object(qrcode.QRCode, 'make', record_make):
            result = prepare_qr('a' * 10000)
        self.assertFalse(result.available)
        self.assertEqual(calls, [(version, False) for version in range(1, MAX_VERSION + 1)])

    def test_empty_content(self):
        result = prepare_qr('')
        self.assertFalse(result.available)
        self.assertIsNone(result.version)
        self.assertEqual(result.total_modules, 0)
        self.assertEqual(result.reason, EMPTY_MESSAGE)
        with self.assertRaises(ValueError):
            result.png()

    def test_availability_does_not_render_an_image(self):
        with patch.object(qrcode.QRCode, 'make_image', side_effect=AssertionError):
            self.assertTrue(prepare_qr('test').available)
            self.assertFalse(prepare_qr('a' * 10000).available)

    def test_png_has_expected_size_and_white_border(self):
        result = prepare_qr('a' * 412)
        with Image.open(io.BytesIO(result.png())) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.size, (result.total_modules * BOX_SIZE,) * 2)
            pixels = image.convert('RGB')
            white = (255, 255, 255)
            edge = BORDER * BOX_SIZE
            for area in [
                (0, 0, image.width, edge),
                (0, image.height - edge, image.width, image.height),
                (0, 0, edge, image.height),
                (image.width - edge, 0, image.width, image.height),
            ]:
                self.assertEqual(pixels.crop(area).getextrema(), ((255, 255),) * 3)
            self.assertEqual(pixels.getpixel((0, 0)), white)
        self.assertEqual(result.total_modules, 85)

    def test_data_uri_contains_png(self):
        result = prepare_qr('test')
        prefix, encoded = result.data_uri().split(',', 1)
        self.assertEqual(prefix, 'data:image/png;base64')
        self.assertEqual(base64.b64decode(encoded), result.png())

    def test_source_text_is_not_changed_or_exposed_in_repr(self):
        text = '[Interface]\r\nPrivateKey = synthetic-secret\n# Пример\n'
        result = prepare_qr(text)
        encoded_text = b''.join(part.data for part in result._qr.data_list)
        self.assertEqual(encoded_text, text.encode('utf-8'))
        self.assertNotIn('synthetic-secret', repr(result))

    def test_typical_wireguard_config(self):
        text = Template(WIREGUARD_TEMPLATE).render(
            private_key='A' * 43 + '=', peer_public_key='B' * 43 + '=',
            client_ipv4='172.16.0.2',
            client_ipv6='2606:4700:110:dead:beef:1234:5678:abcd',
            endpoint='engage.cloudflareclient.com', port=2408,
        )
        self.assertTrue(prepare_qr(text).available)

    def test_unexpected_errors_are_not_suppressed(self):
        with patch.object(qrcode.QRCode, 'make', side_effect=ValueError('unexpected')):
            with self.assertRaisesRegex(ValueError, 'unexpected'):
                prepare_qr('test')


if __name__ == '__main__':
    unittest.main()
