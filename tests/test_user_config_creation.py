from pathlib import Path
import re
import unittest
from unittest.mock import patch

from flask import Flask, redirect, render_template, url_for
from flask_login import LoginManager

from auth import auth_bp
from models import ConfigType, Endpoint, Group, User, db
from routes.user import user_bp


class ConfigCreationEndpointTests(unittest.TestCase):
    def setUp(self):
        # Isolated database; never import app.py or call the real Cloudflare API.
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

        self.app.register_blueprint(user_bp, url_prefix='/user')
        self.app.register_blueprint(auth_bp, url_prefix='/auth')

        @self.app.route('/logout')
        def logout():
            return redirect(url_for('auth.logout'))

        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(username='owner', password_hash='unused')
        self.config_type = ConfigType(name='First endpoint type', config_template='unused')
        # IDs deliberately disagree with alphabetical order, including Cyrillic.
        self.endpoints = [Endpoint(name=name, address='127.0.0.1', port=2408)
                          for name in ['Zulu', 'beta', 'Alpha', 'alpha', 'япония', 'Австрия']]
        self.endpoints[2].config_types.append(self.config_type)
        db.session.add_all([self.user, *self.endpoints])
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user.id)
            session['_fresh'] = True
        mock = patch('warp.client.WarpAPI.create_config', side_effect=AssertionError('Unexpected API call'))
        mock.start()
        self.addCleanup(mock.stop)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def endpoint_options(self, response):
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        select = re.search(r'<select[^>]*name="endpoint_id"[^>]*>(.*?)</select>', html, re.S).group(1)
        return [int(value) for value in re.findall(r'<option[^>]*value="(\d+)"', select)]

    def test_all_endpoints_are_sorted_case_insensitively_with_stable_ties(self):
        with patch('routes.user.render_template', wraps=render_template) as render:
            response = self.client.get('/user/configs/create')
        self.assertEqual(self.endpoint_options(response),
                         [self.endpoints[i].id for i in [2, 3, 1, 0, 5, 4]])
        # The default types must correspond to the first displayed endpoint.
        self.assertEqual(render.call_args.kwargs['form'].config_type_id.choices,
                         [(self.config_type.id, self.config_type.name)])

    def test_group_endpoints_are_sorted_without_showing_other_endpoints(self):
        self.user.group = Group(name='Restricted', endpoints=[self.endpoints[i] for i in [4, 1, 2, 5]])
        db.session.commit()
        response = self.client.get('/user/configs/create')
        self.assertEqual(self.endpoint_options(response),
                         [self.endpoints[i].id for i in [2, 1, 5, 4]])

    def test_empty_group_keeps_alphabetical_fallback_to_all_endpoints(self):
        self.user.group = Group(name='Empty')
        db.session.commit()
        response = self.client.get('/user/configs/create')
        self.assertEqual(self.endpoint_options(response),
                         [self.endpoints[i].id for i in [2, 3, 1, 0, 5, 4]])

    def test_explicit_endpoint_selection_is_preserved(self):
        selected = self.endpoints[0]
        for response in [
            self.client.get(f'/user/configs/create?endpoint_id={selected.id}'),
            self.client.post('/user/configs/create', data={'endpoint_id': selected.id}),
        ]:
            self.assertEqual(self.endpoint_options(response),
                             [self.endpoints[i].id for i in [2, 3, 1, 0, 5, 4]])
            self.assertIn(f'<option value="{selected.id}" selected>', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
