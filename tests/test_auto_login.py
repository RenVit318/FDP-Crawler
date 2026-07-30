"""Tests for auto-login instances (the sandbox deployment)."""

from datetime import datetime, timezone

import pytest

from app import create_app
from app.services.cache import FDPCacheEntry


FDP_URI = 'https://sandbox.example.org'


def _fdp_entry() -> FDPCacheEntry:
    """Cache entry holding one public and one sandbox dataset.

    The FDP itself is deliberately not named "sandbox": the gate keys on dataset
    titles, so a sandbox-named FDP would mask what these tests assert.
    """

    def _dataset(uri: str, title: str) -> dict:
        return {
            'uri': uri,
            'title': title,
            'catalog_uri': f'{FDP_URI}/catalog/1',
            'catalog_title': 'Test Catalog',
            'catalog_homepage': None,
            'fdp_uri': FDP_URI,
            'fdp_title': 'Regional FDP',
            'description': None,
            'publisher': None,
            'creator': None,
            'themes': [],
            'theme_labels': [],
            'keywords': [],
            'contact_point': None,
            'landing_page': None,
            'distributions': [],
            'issued': None,
            'modified': None,
        }

    return FDPCacheEntry(
        fdp_dict={
            'uri': FDP_URI,
            'title': 'Regional FDP',
            'status': 'active',
            'catalogs': [f'{FDP_URI}/catalog/1'],
            'linked_fdps': [],
            'is_index': False,
            'description': None,
            'publisher': None,
            'last_fetched': None,
            'error_message': None,
        },
        datasets=[
            _dataset(f'{FDP_URI}/dataset/public', 'Public Health Records'),
            _dataset(f'{FDP_URI}/dataset/sandbox', 'Sandbox'),
        ],
        last_updated=datetime.now(timezone.utc),
    )


def _make_client(**overrides):
    """Build a test client whose cache holds the public + sandbox datasets."""
    config = {'TESTING': True, 'SECRET_KEY': 'test-secret-key', 'DEFAULT_FDPS': [FDP_URI]}
    config.update(overrides)
    app = create_app(config)
    app.fdp_cache._entries[FDP_URI] = _fdp_entry()
    return app, app.test_client()


@pytest.fixture
def auto_login_client():
    """Client for an instance configured to auto-login as sandbox_query."""
    _, client = _make_client(
        AUTO_LOGIN_USERNAME='sandbox_query',
        AUTO_LOGIN_PASSWORD='sandbox-secret',
    )
    return client


@pytest.fixture
def public_client():
    """Client for a normal instance with no auto-login."""
    _, client = _make_client()
    return client


class TestAutoLoginSession:
    """The session is signed in without any login request."""

    def test_session_user_is_seeded(self, auto_login_client):
        auto_login_client.get('/')
        with auto_login_client.session_transaction() as sess:
            assert sess['user']['username'] == 'sandbox_query'
            assert sess['user']['password'] == 'sandbox-secret'
            assert sess['user']['is_authenticated'] is True

    def test_login_required_routes_are_reachable(self, auto_login_client):
        """No redirect to /auth/login — the SPARQL pages open directly."""
        response = auto_login_client.get('/sparql/')
        assert response.status_code == 200

    def test_no_session_user_without_auto_login(self, public_client):
        public_client.get('/')
        with public_client.session_transaction() as sess:
            assert 'user' not in sess

    def test_public_instance_still_requires_login(self, public_client):
        response = public_client.get('/sparql/')
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_existing_session_user_is_not_overwritten(self, auto_login_client):
        """A user already in the session keeps their identity."""
        with auto_login_client.session_transaction() as sess:
            sess['user'] = {
                'username': 'someone_else',
                'password': 'other',
                'is_authenticated': True,
            }
        auto_login_client.get('/')
        with auto_login_client.session_transaction() as sess:
            assert sess['user']['username'] == 'someone_else'

    def test_logout_is_undone_on_next_request(self, auto_login_client):
        """Logging out cannot strand a visitor on an auto-login instance."""
        auto_login_client.get('/')
        auto_login_client.post('/auth/logout')
        auto_login_client.get('/')
        with auto_login_client.session_transaction() as sess:
            assert sess['user']['username'] == 'sandbox_query'


class TestSandboxVisibility:
    """Auto-login as sandbox_query is what reveals the sandbox datasets."""

    def test_sandbox_dataset_visible_when_auto_logged_in(self, auto_login_client):
        response = auto_login_client.get('/datasets/')
        assert response.status_code == 200
        assert b'Sandbox' in response.data
        assert b'Public Health Records' in response.data

    def test_sandbox_dataset_hidden_on_public_instance(self, public_client):
        response = public_client.get('/datasets/')
        assert response.status_code == 200
        assert b'Public Health Records' in response.data
        assert b'Sandbox' not in response.data


class TestAutoLoginChrome:
    """Login and logout controls are hidden when they cannot do anything."""

    def test_no_login_or_logout_controls(self, auto_login_client):
        response = auto_login_client.get('/')
        assert b'Logout (' not in response.data
        assert b'/auth/login' not in response.data
        assert b'sandbox_query' in response.data

    def test_public_instance_shows_login_link(self, public_client):
        response = public_client.get('/')
        assert b'/auth/login' in response.data


class TestSandboxDataspace:
    """The humanitarian-sandbox dataspace re-exports the humanitarian config."""

    def test_reexports_base_settings(self, monkeypatch):
        monkeypatch.setenv('DATASPACE', 'humanitarian-sandbox')
        app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-key'})

        base_fdps = [
            'https://fairdp.eepa.be',
            'https://fdp.tangaza.ac.ke',
            'https://mutuinifdp.tail1aac55.ts.net',
            'https://aku.edu.et',
            'https://fdp.dhicenter.com',
        ]
        # The sandbox adds its pinned demo FDP on top of the inherited ones.
        assert app.config['DEFAULT_FDPS'] == base_fdps + ['https://fdp.renskievit.com']
        assert app.config['CONTACT_EMAIL'] == 'HDS@eepa.be'
        assert app.config['BRAND_LOGOS']

    def test_pins_demo_fdp_and_default_query(self, monkeypatch):
        monkeypatch.setenv('DATASPACE', 'humanitarian-sandbox')
        app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-key'})

        assert app.config['PINNED_FDPS'] == ['https://fdp.renskievit.com']
        assert 'reg:GRP-A17' in app.config['DEFAULT_SPARQL_QUERY']

    def test_public_dataspace_has_no_pins_or_default_query(self, monkeypatch):
        monkeypatch.setenv('DATASPACE', 'humanitarian')
        app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-key'})

        assert not app.config.get('PINNED_FDPS')
        assert not app.config.get('DEFAULT_SPARQL_QUERY')


class TestPinnedFDPs:
    """PINNED_FDPS stay connected in every session, however the session started."""

    def test_pinned_fdp_added_to_fresh_session(self):
        _, client = _make_client(PINNED_FDPS=['https://pinned.example.org'])
        with client:
            client.get('/')
            from flask import session
            assert 'https://pinned.example.org' in session['fdp_uris']

    def test_pinned_fdp_restored_in_existing_session(self):
        """A session seeded before the FDP was pinned picks it up next request."""
        _, client = _make_client(PINNED_FDPS=['https://pinned.example.org'])
        with client:
            with client.session_transaction() as sess:
                sess['fdp_uris'] = [FDP_URI]
            client.get('/')
            from flask import session
            assert session['fdp_uris'] == [FDP_URI, 'https://pinned.example.org']

    def test_admin_cannot_remove_pinned_fdp(self):
        from app.utils import get_uri_hash

        _, client = _make_client(PINNED_FDPS=['https://pinned.example.org'])
        with client:
            with client.session_transaction() as sess:
                sess['is_admin'] = True
            client.get('/')
            response = client.post(
                f'/fdp/{get_uri_hash("https://pinned.example.org")}/remove',
                follow_redirects=True,
            )
            assert b'cannot be removed' in response.data
            from flask import session
            assert 'https://pinned.example.org' in session['fdp_uris']

    def test_overrides_identity(self, monkeypatch):
        monkeypatch.setenv('DATASPACE', 'humanitarian-sandbox')
        app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-key'})

        assert app.config['SITE_NAME'] == 'Humanitarian Data Space (Sandbox)'
        assert app.config['SITE_BANNER']

    def test_banner_is_rendered(self, monkeypatch):
        monkeypatch.setenv('DATASPACE', 'humanitarian-sandbox')
        app = create_app(
            {'TESTING': True, 'SECRET_KEY': 'test-secret-key', 'DEFAULT_FDPS': []}
        )
        response = app.test_client().get('/')
        assert b'env-banner' in response.data
        assert b'Sandbox environment' in response.data
