import io
from pathlib import Path
import unittest
from unittest.mock import patch

from flask import Flask, redirect, url_for
from flask_login import LoginManager
from PIL import Image

from auth import auth_bp
from models import Config, ConfigType, Endpoint, User, db
from routes.user import user_bp
from utils.qr import EMPTY_MESSAGE, TOO_LARGE_MESSAGE, prepare_qr


class QRRouteTests(unittest.TestCase):
    def setUp(self):
        # Do not import app.py: its factory initializes the production /data DB.
        root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, template_folder=str(root / 'templates'),
                         static_folder=str(root / 'static'))
        self.app.config.update(
            TESTING=True,
            SECRET_KEY='test-only',
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            WTF_CSRF_ENABLED=False,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)
        login_manager.login_view = 'auth.login'

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(user_bp, url_prefix='/user')
        self.app.register_blueprint(auth_bp, url_prefix='/auth')

        @self.app.route('/logout')
        def logout():
            return redirect(url_for('auth.logout'))

        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(username='owner', password_hash='unused')
        other_user = User(username='other', password_hash='unused')
        endpoint = Endpoint(name='Test endpoint', address='127.0.0.1', port=2408)
        config_type = ConfigType(name='WireGuard', config_template='unused')
        db.session.add_all([user, other_user, endpoint, config_type])
        db.session.flush()
        self.owner_id = user.id
        self.small = self.add_config(user, endpoint, config_type, '[Interface]\n# test\n')
        self.large = self.add_config(user, endpoint, config_type, 'a' * 10000)
        self.empty = self.add_config(user, endpoint, config_type, '')
        self.foreign = self.add_config(other_user, endpoint, config_type, 'foreign secret')
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def add_config(self, user, endpoint, config_type, text):
        config = Config(
            name='Test config', user_id=user.id, endpoint_id=endpoint.id,
            config_type_id=config_type.id, config_content=text,
            cloudflare_id='test-device', cloudflare_token='test-token',
            private_key='test-private', public_key='test-public',
            peer_public_key='test-peer', client_ipv4='172.16.0.2',
            client_ipv6='2606:4700::2',
        )
        db.session.add(config)
        db.session.flush()
        return config.id

    def test_lists_only_offer_available_qr(self):
        for path in ['/user/dashboard', '/user/configs']:
            with self.subTest(path=path):
                # One check per owned configuration, no PNG generation.
                with patch('routes.user.prepare_qr', wraps=prepare_qr) as prepare:
                    with patch('utils.qr.QRResult.png', side_effect=AssertionError):
                        response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(prepare.call_count, 3)
                html = response.get_data(as_text=True)
                self.assertEqual(html.count(f'/user/configs/{self.small}/qr'), 2)
                for config_id in [self.large, self.empty, self.foreign]:
                    self.assertNotIn(f'/user/configs/{config_id}/qr', html)

    def test_large_config_page_works_without_offering_qr(self):
        response = self.client.get(f'/user/configs/{self.large}')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn(TOO_LARGE_MESSAGE, html)
        self.assertIn('a' * 10000, html)
        self.assertIn('copyToClipboard()', html)
        self.assertIn(f'/user/configs/{self.large}/download', html)
        self.assertNotIn(f'/user/configs/{self.large}/qr', html)
        self.assertNotIn('data:image/png;base64,', html)
        self.assertNotIn('Отсканируйте QR-код выше', html)
        self.assertIn('Импорт из файла', html)

    def test_small_config_page_offers_qr_and_scan_instructions(self):
        response = self.client.get(f'/user/configs/{self.small}')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data:image/png;base64,', html)
        self.assertIn(f'/user/configs/{self.small}/qr', html)
        self.assertIn('Отсканируйте QR-код выше', html)
        self.assertNotIn('max-width: 200px', html)

    def test_unavailable_qr_returns_422_and_download_link(self):
        for config_id, reason in [(self.large, TOO_LARGE_MESSAGE), (self.empty, EMPTY_MESSAGE)]:
            with self.subTest(config_id=config_id):
                response = self.client.get(f'/user/configs/{config_id}/qr')
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.mimetype, 'text/html')
                html = response.get_data(as_text=True)
                self.assertIn(reason, html)
                self.assertIn(f'/user/configs/{config_id}/download', html)
                self.assertNotIn('data:image/png;base64,', html)

    def test_empty_config_page_has_correct_reason(self):
        response = self.client.get(f'/user/configs/{self.empty}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(EMPTY_MESSAGE, response.get_data(as_text=True))
        self.assertNotIn(TOO_LARGE_MESSAGE, response.get_data(as_text=True))

    def test_png_endpoint_uses_the_shared_generator(self):
        response = self.client.get(f'/user/configs/{self.small}/qr')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        text = db.session.get(Config, self.small).config_content
        self.assertEqual(response.data, prepare_qr(text).png())
        with Image.open(io.BytesIO(response.data)) as image:
            self.assertEqual(image.format, 'PNG')

    def test_large_config_download_preserves_original_content(self):
        response = self.client.get(f'/user/configs/{self.large}/download')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'a' * 10000)
        self.assertIn('attachment;', response.headers['Content-Disposition'])

    def test_foreign_and_missing_configs_are_rejected_before_qr_processing(self):
        with patch('routes.user.prepare_qr', side_effect=AssertionError):
            for config_id in [self.foreign, 99999]:
                for suffix in ['', '/qr', '/download']:
                    with self.subTest(config_id=config_id, suffix=suffix):
                        response = self.client.get(f'/user/configs/{config_id}{suffix}')
                        self.assertEqual(response.status_code, 404)

    def test_anonymous_requests_require_login_before_qr_processing(self):
        client = self.app.test_client()
        with patch('routes.user.prepare_qr', side_effect=AssertionError):
            for path in ['/user/dashboard', '/user/configs',
                         f'/user/configs/{self.small}', f'/user/configs/{self.small}/qr']:
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 302)
                    self.assertIn('/auth/login', response.headers['Location'])

    def test_paginated_list_only_checks_current_page(self):
        original = db.session.get(Config, self.small)
        for index in range(7):
            self.add_config(original.owner, original.endpoint_ref, original.config_type,
                            f'page test {index}')
        db.session.commit()
        for page, expected_count in [(1, 6), (2, 4), (3, 0)]:
            with self.subTest(page=page):
                with patch('routes.user.prepare_qr', wraps=prepare_qr) as prepare:
                    response = self.client.get(f'/user/configs?page={page}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(prepare.call_count, expected_count)

        # The dashboard also displays only the six most recent configurations.
        with patch('routes.user.prepare_qr', wraps=prepare_qr) as prepare:
            response = self.client.get('/user/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(prepare.call_count, 6)


if __name__ == '__main__':
    unittest.main()
