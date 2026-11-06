from datetime import datetime
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from flask import Flask, g, redirect, url_for
from flask_login import LoginManager
from sqlalchemy.exc import SQLAlchemyError
from flask_sqlalchemy.query import Query

from auth import auth_bp
from models import Config, ConfigType, Endpoint, User, db, endpoint_config_types
from routes.admin import admin_bp
from routes.user import user_bp


class AdminConfigTests(unittest.TestCase):
    def setUp(self):
        # Isolated in-memory database; never import the production app factory.
        root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, template_folder=str(root / 'templates'),
                         static_folder=str(root / 'static'))
        self.app.config.update(
            TESTING=True, SECRET_KEY='test-only',
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_TRACK_MODIFICATIONS=False, WTF_CSRF_ENABLED=False,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)
        login_manager.login_view = 'auth.login'

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(admin_bp, url_prefix='/admin')
        self.app.register_blueprint(user_bp, url_prefix='/user')
        self.app.register_blueprint(auth_bp, url_prefix='/auth')

        @self.app.route('/logout')
        def logout():
            return redirect(url_for('auth.logout'))

        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.admin = User(username='admin', password_hash='unused', is_admin=True)
        self.owner = User(username='owner', password_hash='unused')
        self.other = User(username='other', password_hash='unused')
        self.original_type = ConfigType(name='WireGuard', config_template='original')
        self.target_type = ConfigType(
            name='Clash',
            config_template='{{ private_key }}|{{ public_key }}|{{ peer_public_key }}|'
                            '{{ client_ipv4 }}|{{ client_ipv6 }}|{{ endpoint }}|{{ port }}|'
                            '{{ cloudflare_id }}|{{ token }}',
        )
        self.inactive_type = ConfigType(name='Inactive', config_template='inactive', is_active=False)
        self.unsupported_type = ConfigType(name='Unsupported', config_template='unsupported')
        self.endpoint = Endpoint(name='Test endpoint', address='127.0.0.1', port=2408)
        self.endpoint.config_types = [self.original_type, self.target_type, self.inactive_type]
        db.session.add_all([self.admin, self.owner, self.other, self.endpoint, self.unsupported_type])
        db.session.flush()
        self.config = self.add_config(self.owner, 'Owner configuration')
        self.foreign = self.add_config(self.other, 'Other configuration')
        db.session.commit()
        self.client = self.app.test_client()
        self.login(self.admin)
        for method in ['create_config', 'delete_config']:
            mock = patch(f'warp.client.WarpAPI.{method}', side_effect=AssertionError('Unexpected API call'))
            mock.start()
            self.addCleanup(mock.stop)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def login(self, user):
        g.pop('_login_user', None)
        with self.client.session_transaction() as session:
            session.clear()
            if user:
                session['_user_id'] = str(user.id)
                session['_fresh'] = True

    def add_config(self, owner, name):
        config = Config(
            name=name, owner=owner, endpoint_ref=self.endpoint, config_type=self.original_type,
            cloudflare_id='device-id', cloudflare_token='device-token',
            private_key='private-key', public_key='public-key', peer_public_key='peer-key',
            client_ipv4='172.16.0.2', client_ipv6='2606:4700::2',
            config_content='original content', created_at=datetime(2026, 1, 1),
        )
        db.session.add(config)
        db.session.flush()
        return config

    def change_type(self, type_id=None, **kwargs):
        return self.client.post(f'/admin/configs/{self.config.id}/change-type',
                                data={'config_type_id': type_id or self.target_type.id}, **kwargs)

    def snapshot(self):
        return {column.name: getattr(self.config, column.name) for column in Config.__table__.columns}

    def test_admin_list_and_navigation_include_every_owner(self):
        response = self.client.get('/admin/configs')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for config in [self.config, self.foreign]:
            self.assertIn(config.name, html)
            for suffix in ['', '/download', '/change-type']:
                self.assertIn(f'/admin/configs/{config.id}{suffix}', html)
        self.assertIn('WireGuard', html)
        self.assertIn('01.01.2026', html)
        self.assertIn('href="/admin/configs" class="app-bar-nav-item active"', html)
        self.assertNotIn('href="/user/configs" class="app-bar-nav-item', html)

    def test_pagination_is_stable_with_equal_creation_dates(self):
        for index in range(10):
            self.add_config(self.owner, f'Pagination config {index}')
        db.session.commit()
        first = self.client.get('/admin/configs').get_data(as_text=True)
        second = self.client.get('/admin/configs?page=2').get_data(as_text=True)
        self.assertNotIn('Owner configuration', first)
        self.assertNotIn('Other configuration', first)
        self.assertIn('Owner configuration', second)
        self.assertIn('Other configuration', second)
        self.assertNotIn('Pagination config', second)

    def test_admin_can_view_download_and_get_qr_for_other_owner(self):
        config_id = self.config.id
        response = self.client.get(f'/admin/configs/{config_id}')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for suffix in ['/download', '/qr', '/change-type']:
            self.assertIn(f'/admin/configs/{config_id}{suffix}', html)
        self.assertNotIn(f'/user/configs/{config_id}', html)
        self.assertNotIn('id="deleteModal"', html)
        response = self.client.get(f'/admin/configs/{config_id}/download')
        self.assertEqual(response.data, b'original content')
        self.assertIn('.conf', response.headers['Content-Disposition'])
        response = self.client.get(f'/admin/configs/{config_id}/qr')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')

    def test_admin_unavailable_qr_links_stay_in_admin_routes(self):
        self.config.config_content = 'a' * 10000
        db.session.commit()
        response = self.client.get(f'/admin/configs/{self.config.id}/qr')
        self.assertEqual(response.status_code, 422)
        html = response.get_data(as_text=True)
        self.assertIn(f'/admin/configs/{self.config.id}/download', html)
        self.assertNotIn(f'/user/configs/{self.config.id}', html)

    def test_anonymous_and_regular_users_cannot_use_admin_routes(self):
        for user in [None, self.owner]:
            self.login(user)
            before = self.snapshot()
            for suffix in ['', '/download', '/qr', '/change-type']:
                response = self.client.get(f'/admin/configs/{self.config.id}{suffix}')
                self.assertEqual(response.status_code, 302)
                self.assertIn('/auth/login', response.headers['Location'])
            self.assertEqual(self.client.get('/admin/configs').status_code, 302)
            self.assertEqual(self.change_type().status_code, 302)
            self.assertEqual(self.snapshot(), before)

    def test_user_routes_still_restrict_access_to_owner(self):
        self.login(self.owner)
        for suffix in ['', '/download', '/qr', '/edit']:
            self.assertEqual(self.client.get(f'/user/configs/{self.foreign.id}{suffix}').status_code, 404)
        for suffix in ['/edit', '/delete']:
            response = self.client.post(f'/user/configs/{self.foreign.id}{suffix}', data={'name': 'changed'})
            self.assertEqual(response.status_code, 404)

    def test_type_choices_exclude_current_inactive_and_unsupported_types(self):
        response = self.client.get(f'/admin/configs/{self.config.id}/change-type')
        html = response.get_data(as_text=True)
        self.assertIn(f'value="{self.target_type.id}"', html)
        for config_type in [self.original_type, self.inactive_type, self.unsupported_type]:
            self.assertNotIn(f'value="{config_type.id}"', html)

    def test_type_change_only_updates_type_and_content(self):
        before = self.snapshot()
        response = self.change_type()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith(f'/admin/configs/{self.config.id}'))
        db.session.expire_all()
        self.assertEqual(self.config.config_type_id, self.target_type.id)
        self.assertEqual(self.config.config_content,
                         'private-key|public-key|peer-key|172.16.0.2|2606:4700::2|127.0.0.1|2408|device-id|device-token')
        after = self.snapshot()
        for key in before.keys() - {'config_type_id', 'config_content'}:
            self.assertEqual(after[key], before[key], key)
        response = self.client.get(f'/admin/configs/{self.config.id}/download')
        self.assertIn('.yaml', response.headers['Content-Disposition'])
        self.login(self.owner)
        response = self.client.get(f'/user/configs/{self.config.id}/download')
        self.assertEqual(response.get_data(as_text=True), self.config.config_content)
        self.assertIn('.yaml', response.headers['Content-Disposition'])

    def test_invalid_types_do_not_change_config(self):
        before = self.snapshot()
        for type_id in [self.original_type.id, self.inactive_type.id,
                        self.unsupported_type.id, 99999, 'invalid']:
            response = self.change_type(type_id)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.snapshot(), before)

    def test_invalid_or_empty_templates_preserve_original_config(self):
        before = self.snapshot()
        for template in ['{{ missing }}', '{% broken', '', '   ']:
            self.target_type.config_template = template
            db.session.commit()
            response = self.change_type()
            self.assertEqual(response.status_code, 200)
            self.assertIn('Исходный конфиг сохранён', response.get_data(as_text=True))
            db.session.expire_all()
            self.assertEqual(self.snapshot(), before)

    def test_commit_failure_rolls_back_type_and_content(self):
        before = self.snapshot()
        with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('commit failed')):
            response = self.change_type()
        self.assertEqual(response.status_code, 200)
        db.session.expire_all()
        self.assertEqual(self.snapshot(), before)

    def test_missing_configs_return_404(self):
        for suffix in ['', '/download', '/qr', '/change-type']:
            self.assertEqual(self.client.get(f'/admin/configs/99999{suffix}').status_code, 404)
        self.assertEqual(self.client.post('/admin/configs/99999/change-type').status_code, 404)

    def test_no_alternative_types_and_legacy_config_without_type(self):
        self.endpoint.config_types = [self.original_type]
        db.session.commit()
        response = self.client.get(f'/admin/configs/{self.config.id}/change-type')
        self.assertIn('нет других активных типов', response.get_data(as_text=True))
        self.assertEqual(self.change_type().status_code, 200)
        self.config.config_type = None
        db.session.commit()
        self.assertEqual(self.client.get('/admin/configs').status_code, 200)
        self.assertEqual(self.client.get(f'/admin/configs/{self.config.id}').status_code, 200)
        response = self.change_type(self.original_type.id)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.config.config_type_id, self.original_type.id)

    def test_type_change_requires_valid_csrf_token(self):
        self.app.config['WTF_CSRF_ENABLED'] = True
        before = self.snapshot()
        self.assertEqual(self.change_type().status_code, 200)
        self.assertEqual(self.snapshot(), before)
        response = self.client.get(f'/admin/configs/{self.config.id}/change-type')
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)).group(1)
        response = self.client.post(f'/admin/configs/{self.config.id}/change-type',
                                    data={'config_type_id': self.target_type.id, 'csrf_token': token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.config.config_type_id, self.target_type.id)

    def test_type_list_shows_counts_for_all_owners_and_zero_usage(self):
        response = self.client.get('/admin/config-types')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        rows = re.findall(r'<tr>(.*?)</tr>', html, re.S)
        for config_type, count in [(self.original_type, 2), (self.target_type, 0),
                                   (self.inactive_type, 0), (self.unsupported_type, 0)]:
            row = next(row for row in rows if f'<strong>{config_type.name}</strong>' in row)
            self.assertIn(f'<td>{count}</td>', row)
            delete_url = f'/admin/config-types/{config_type.id}/delete'
            if count:
                self.assertNotIn(delete_url, row)
                self.assertIn('disabled', row)
            else:
                self.assertIn(delete_url, row)
                self.assertIn('onsubmit="return confirm(', row)

    def test_delete_unused_type_with_or_without_endpoint_links(self):
        for config_type in [self.unsupported_type, self.target_type, self.inactive_type]:
            type_id = config_type.id
            response = self.client.post(f'/admin/config-types/{type_id}/delete', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn('успешно удален', response.get_data(as_text=True))
            db.session.expire_all()
            self.assertIsNone(db.session.get(ConfigType, type_id))
            links = db.session.execute(db.select(endpoint_config_types).where(
                endpoint_config_types.c.config_type_id == type_id)).all()
            self.assertEqual(links, [])
            self.assertEqual(Endpoint.query.count(), 1)
            self.assertEqual(Config.query.count(), 2)
        self.assertEqual(self.endpoint.config_types, [self.original_type])

    def test_used_type_cannot_be_deleted_by_direct_post(self):
        before = [self.snapshot(), self.foreign.config_type_id, self.foreign.config_content]
        type_id = self.original_type.id
        response = self.client.post(f'/admin/config-types/{type_id}/delete', follow_redirects=True)
        self.assertIn('Он используется в 2 конфигурациях', response.get_data(as_text=True))
        db.session.expire_all()
        self.assertIsNotNone(db.session.get(ConfigType, type_id))
        self.assertEqual([self.snapshot(), self.foreign.config_type_id, self.foreign.config_content], before)
        self.assertIn(self.original_type, self.endpoint.config_types)

    def test_delete_rechecks_usage_after_list_was_loaded(self):
        self.client.get('/admin/config-types')
        self.foreign.config_type = self.target_type
        db.session.commit()
        type_id = self.target_type.id
        response = self.client.post(f'/admin/config-types/{type_id}/delete', follow_redirects=True)
        self.assertIn('Он используется в 1 конфигурациях', response.get_data(as_text=True))
        db.session.expire_all()
        self.assertEqual(self.foreign.config_type_id, type_id)
        self.assertIsNotNone(db.session.get(ConfigType, type_id))

    def test_type_delete_failure_rolls_back_endpoint_links_and_hides_error(self):
        type_id = self.target_type.id
        with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('synthetic-secret')):
            response = self.client.post(f'/admin/config-types/{type_id}/delete', follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertIn('Изменения отменены', html)
        self.assertNotIn('synthetic-secret', html)
        db.session.expire_all()
        self.assertIsNotNone(db.session.get(ConfigType, type_id))
        self.assertIn(self.target_type, self.endpoint.config_types)

    def test_conditional_delete_preserves_configs_even_if_preliminary_count_is_stale(self):
        type_id = self.original_type.id
        before = self.snapshot()
        # Simulate a zero count that is no longer valid at DELETE time.
        with patch.object(Query, 'count', return_value=0):
            response = self.client.post(f'/admin/config-types/{type_id}/delete', follow_redirects=True)
        self.assertIn('Он уже используется', response.get_data(as_text=True))
        db.session.expire_all()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.foreign.config_type_id, type_id)
        self.assertIn(self.original_type, self.endpoint.config_types)

    def test_type_actions_require_admin_and_post(self):
        type_id = self.target_type.id
        for action in ['delete', 'toggle']:
            self.assertEqual(self.client.get(f'/admin/config-types/{type_id}/{action}').status_code, 405)
        for user in [None, self.owner]:
            self.login(user)
            response = self.client.get('/admin/config-types')
            self.assertEqual(response.status_code, 302)
            self.assertIn('/auth/login', response.headers['Location'])
            for action in ['delete', 'toggle']:
                response = self.client.post(f'/admin/config-types/{type_id}/{action}')
                self.assertEqual(response.status_code, 302)
                self.assertIn('/auth/login', response.headers['Location'])
                self.assertIsNotNone(db.session.get(ConfigType, type_id))
                self.assertTrue(self.target_type.is_active)

    def test_missing_type_actions_return_404(self):
        for action in ['delete', 'toggle']:
            self.assertEqual(self.client.post(f'/admin/config-types/99999/{action}').status_code, 404)

    def test_type_actions_require_valid_csrf_token(self):
        self.app.config['WTF_CSRF_ENABLED'] = True
        type_id = self.target_type.id
        for action in ['delete', 'toggle']:
            for data in [{}, {'csrf_token': 'invalid'}]:
                response = self.client.post(f'/admin/config-types/{type_id}/{action}', data=data)
                self.assertEqual(response.status_code, 302)
                self.assertIsNotNone(db.session.get(ConfigType, type_id))
                self.assertTrue(self.target_type.is_active)
        html = self.client.get('/admin/config-types').get_data(as_text=True)
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
        response = self.client.post(f'/admin/config-types/{type_id}/toggle', data={'csrf_token': token})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.target_type.is_active)
        response = self.client.post(f'/admin/config-types/{type_id}/delete', data={'csrf_token': token})
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(db.session.get(ConfigType, type_id))


if __name__ == '__main__':
    unittest.main()
