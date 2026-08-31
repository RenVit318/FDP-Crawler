"""Tests for Keycloak-role-based admin access and the session hardening."""

import time
from datetime import timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.services import keycloak
from app.services.admin_service import verify_admin


KEYCLOAK_CONFIG = {
    'TESTING': True,
    'SECRET_KEY': 'test-secret-key',
    'DEFAULT_FDPS': [],
    'KEYCLOAK_SERVER_URL': 'https://auth.example.org',
    'KEYCLOAK_REALM': 'dataspace',
    'KEYCLOAK_CLIENT_ID': 'hds',
    'KEYCLOAK_ADMIN_ROLE': 'hds-admin',
}


@pytest.fixture
def kc_app():
    return create_app(dict(KEYCLOAK_CONFIG))


@pytest.fixture
def kc_client(kc_app):
    return kc_app.test_client()


def _token(roles=None, client_roles=None, username='alice'):
    """Build a token payload shaped like Authlib's authorize_access_token()."""
    claims = {'preferred_username': username, 'sub': 'uuid-1'}
    if roles is not None:
        claims['realm_access'] = {'roles': roles}
    if client_roles is not None:
        claims['resource_access'] = {'hds': {'roles': client_roles}}
    return {
        'access_token': 'access-abc',
        'refresh_token': 'refresh-abc',
        'id_token': 'id-abc',
        'expires_at': time.time() + 300,
        'userinfo': claims,
    }


def _sign_in(kc_app, kc_client, token):
    with patch.object(
        type(kc_app.keycloak_oauth.keycloak),
        'authorize_access_token',
        return_value=token,
    ):
        return kc_client.get('/auth/keycloak/callback?code=x&state=y')


class TestRoleExtraction:
    """Roles are read from realm roles and this client's roles alike."""

    def test_realm_role_grants_admin(self, kc_app):
        with kc_app.test_request_context():
            claims = _token(roles=['hds-admin', 'offline_access'])['userinfo']
            assert keycloak.has_admin_role(claims) is True

    def test_client_role_grants_admin(self, kc_app):
        with kc_app.test_request_context():
            claims = _token(client_roles=['hds-admin'])['userinfo']
            assert keycloak.has_admin_role(claims) is True

    def test_other_roles_do_not_grant_admin(self, kc_app):
        with kc_app.test_request_context():
            claims = _token(roles=['data-user', 'offline_access'])['userinfo']
            assert keycloak.has_admin_role(claims) is False

    def test_missing_roles_claim_denies_and_warns(self, kc_app, caplog):
        """A missing mapper must deny, and say so — it is easy to misdiagnose."""
        with kc_app.test_request_context():
            assert keycloak.has_admin_role({'preferred_username': 'alice'}) is False
        assert 'no roles claim' in caplog.text

    def test_roles_from_other_client_ignored(self, kc_app):
        """A role on a different client must not grant admin here."""
        with kc_app.test_request_context():
            claims = {
                'preferred_username': 'alice',
                'resource_access': {'other-client': {'roles': ['hds-admin']}},
            }
            assert keycloak.has_admin_role(claims) is False


class TestSingleButtonElevation:
    """One sign-in: the role decides whether the panels appear."""

    def test_admin_role_elevates_session(self, kc_app, kc_client):
        _sign_in(kc_app, kc_client, _token(roles=['hds-admin']))

        with kc_client.session_transaction() as sess:
            assert sess['user']['username'] == 'alice'
            assert sess['is_admin'] is True
            assert sess['admin_username'] == 'alice'

    def test_admin_panel_reachable_after_role_login(self, kc_app, kc_client):
        _sign_in(kc_app, kc_client, _token(roles=['hds-admin']))
        response = kc_client.get('/admin/')
        assert response.status_code == 200

    def test_non_admin_signs_in_without_elevation(self, kc_app, kc_client):
        _sign_in(kc_app, kc_client, _token(roles=['data-user']))

        with kc_client.session_transaction() as sess:
            assert sess['user']['username'] == 'alice'
            assert sess.get('is_admin') is None

        response = kc_client.get('/admin/', follow_redirects=False)
        assert response.status_code == 302

    def test_login_does_not_inherit_stale_elevation(self, kc_app, kc_client):
        """A non-admin login must clear admin rights left in the session."""
        with kc_client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_username'] = 'someone-else'

        _sign_in(kc_app, kc_client, _token(roles=['data-user']))

        with kc_client.session_transaction() as sess:
            assert sess.get('is_admin') is None
            assert sess.get('admin_username') is None

    def test_logout_drops_admin_rights(self, kc_app, kc_client):
        """Sessions are coupled: portal logout ends admin too."""
        _sign_in(kc_app, kc_client, _token(roles=['hds-admin']))

        with patch.object(keycloak, '_server_metadata', return_value={}):
            kc_client.post('/auth/logout')

        with kc_client.session_transaction() as sess:
            assert sess.get('is_admin') is None
            assert 'user' not in sess

    def test_no_separate_admin_link_in_nav(self, kc_client):
        """The nav offers one login, not a second admin one."""
        response = kc_client.get('/')
        assert b'/admin/login' not in response.data


class TestPasswordAdminLoginClosed:
    """With Keycloak configured, the local password account is not a way in."""

    def test_admin_login_redirects_to_keycloak(self, kc_client):
        response = kc_client.get('/admin/login')
        assert response.status_code == 302
        assert '/auth/keycloak/login' in response.location

    def test_admin_login_post_does_not_authenticate(self, kc_client):
        """Even a POST straight at the route cannot elevate."""
        response = kc_client.post('/admin/login', data={
            'username': 'admin',
            'password': 'admin',
        })
        assert response.status_code == 302
        with kc_client.session_transaction() as sess:
            assert sess.get('is_admin') is None

    def test_verify_admin_refuses_when_keycloak_enabled(self, kc_app):
        """Defence in depth: the service layer refuses too, not just the route."""
        with kc_app.test_request_context():
            assert verify_admin('admin', 'admin') is False

    def test_password_login_still_available_without_keycloak(self, client):
        """Local development, where Keycloak is unconfigured, keeps working."""
        response = client.get('/admin/login')
        assert response.status_code == 200
        assert b'Username' in response.data


class TestSessionHardening:
    """Cookie and lifetime settings."""

    def test_secure_cookie_follows_force_https(self):
        app = create_app(dict(KEYCLOAK_CONFIG, FORCE_HTTPS=True))
        assert app.config['SESSION_COOKIE_SECURE'] is True

    def test_cookie_not_secure_for_local_http_dev(self, kc_app):
        assert kc_app.config['SESSION_COOKIE_SECURE'] is False

    def test_session_lifetime_is_eight_hours(self, kc_app):
        assert kc_app.config['PERMANENT_SESSION_LIFETIME'] == timedelta(hours=8)

    def test_cookie_flags_still_set(self, kc_app):
        assert kc_app.config['SESSION_COOKIE_HTTPONLY'] is True
        assert kc_app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'


class TestTlsVerificationDefault:
    """FDP scraping verifies certificates unless explicitly opted out."""

    def test_verify_ssl_on_by_default(self, kc_app):
        assert kc_app.config['FDP_VERIFY_SSL'] is True
