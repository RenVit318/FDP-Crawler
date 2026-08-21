"""Tests for the optional Keycloak / OIDC login and bearer-token query path."""

import time
from unittest.mock import patch
from urllib.parse import quote_plus

import pytest
import responses

from app import create_app
from app.models import SPARQLQuery, EndpointCredentials
from app.services import keycloak
from app.services.sparql_client import SPARQLClient


KEYCLOAK_CONFIG = {
    'TESTING': True,
    'SECRET_KEY': 'test-secret-key',
    'DEFAULT_FDPS': [],
    'KEYCLOAK_SERVER_URL': 'https://auth.example.org',
    'KEYCLOAK_REALM': 'dataspace',
    'KEYCLOAK_CLIENT_ID': 'portal',
    'KEYCLOAK_CLIENT_SECRET': 'portal-secret',
}

TOKEN_ENDPOINT = (
    'https://auth.example.org/realms/dataspace/protocol/openid-connect/token'
)


@pytest.fixture
def kc_app():
    """App with Keycloak configured."""
    return create_app(dict(KEYCLOAK_CONFIG))


@pytest.fixture
def kc_client(kc_app):
    """Test client for the Keycloak-enabled app."""
    return kc_app.test_client()


class TestKeycloakDisabled:
    """Keycloak is unconfigured by default and must change nothing."""

    def test_not_enabled_without_config(self, app):
        with app.test_request_context():
            assert keycloak.is_enabled() is False
            assert keycloak.get_client() is None

    def test_login_page_has_no_keycloak_button(self, client):
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Sign in with Keycloak' not in response.data

    def test_keycloak_login_route_rejects(self, client):
        response = client.get('/auth/keycloak/login', follow_redirects=True)
        assert b'Keycloak login is not configured' in response.data

    def test_keycloak_callback_route_rejects(self, client):
        response = client.get('/auth/keycloak/callback', follow_redirects=True)
        assert b'Keycloak login is not configured' in response.data

    def test_password_login_still_works(self, client):
        """The original login flow is untouched."""
        response = client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass',
        }, follow_redirects=True)

        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess['user']['username'] == 'testuser'
            assert sess['user']['auth_method'] == 'password'


class TestKeycloakEnabled:
    """Behaviour once the KEYCLOAK_* settings are present."""

    def test_is_enabled(self, kc_app):
        with kc_app.test_request_context():
            assert keycloak.is_enabled() is True

    def test_login_page_offers_both_methods(self, kc_client):
        response = kc_client.get('/auth/login')
        assert response.status_code == 200
        assert b'Sign in with Keycloak' in response.data
        # The username/password form remains available alongside it.
        assert b'Username' in response.data
        assert b'Password' in response.data

    def test_login_redirects_to_keycloak(self, kc_client):
        """The authorize redirect points at the configured realm."""
        with patch.object(
            keycloak, '_server_metadata', return_value={}
        ), responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                'https://auth.example.org/realms/dataspace/.well-known/openid-configuration',
                json={
                    'issuer': 'https://auth.example.org/realms/dataspace',
                    'authorization_endpoint': (
                        'https://auth.example.org/realms/dataspace'
                        '/protocol/openid-connect/auth'
                    ),
                    'token_endpoint': TOKEN_ENDPOINT,
                },
            )
            response = kc_client.get('/auth/keycloak/login')

        assert response.status_code == 302
        assert 'auth.example.org' in response.location
        assert 'client_id=portal' in response.location

    def test_login_stashes_next(self, kc_client):
        """?next survives the round trip to Keycloak via the session."""
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                'https://auth.example.org/realms/dataspace/.well-known/openid-configuration',
                json={
                    'issuer': 'https://auth.example.org/realms/dataspace',
                    'authorization_endpoint': (
                        'https://auth.example.org/realms/dataspace'
                        '/protocol/openid-connect/auth'
                    ),
                    'token_endpoint': TOKEN_ENDPOINT,
                },
            )
            kc_client.get('/auth/keycloak/login?next=/sparql/')

        with kc_client.session_transaction() as sess:
            assert sess['keycloak_next'] == '/sparql/'

    def test_login_ignores_external_next(self, kc_client):
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                'https://auth.example.org/realms/dataspace/.well-known/openid-configuration',
                json={
                    'issuer': 'https://auth.example.org/realms/dataspace',
                    'authorization_endpoint': (
                        'https://auth.example.org/realms/dataspace'
                        '/protocol/openid-connect/auth'
                    ),
                    'token_endpoint': TOKEN_ENDPOINT,
                },
            )
            kc_client.get('/auth/keycloak/login?next=http://evil.com')

        with kc_client.session_transaction() as sess:
            assert 'keycloak_next' not in sess

    def test_callback_signs_user_in(self, kc_app, kc_client):
        """A successful code exchange stores the user and the tokens."""
        fake_token = {
            'access_token': 'access-abc',
            'refresh_token': 'refresh-abc',
            'id_token': 'id-abc',
            'expires_at': time.time() + 300,
            'userinfo': {'preferred_username': 'alice', 'sub': 'uuid-1'},
        }

        with patch.object(
            type(kc_app.keycloak_oauth.keycloak),
            'authorize_access_token',
            return_value=fake_token,
        ):
            response = kc_client.get(
                '/auth/keycloak/callback?code=x&state=y', follow_redirects=True
            )

        assert response.status_code == 200
        with kc_client.session_transaction() as sess:
            assert sess['user']['username'] == 'alice'
            assert sess['user']['auth_method'] == 'keycloak'
            assert sess['user']['password'] == ''
            assert sess['keycloak_tokens']['access_token'] == 'access-abc'
            assert sess['keycloak_tokens']['refresh_token'] == 'refresh-abc'

    def test_callback_failure_returns_to_login(self, kc_app, kc_client):
        with patch.object(
            type(kc_app.keycloak_oauth.keycloak),
            'authorize_access_token',
            side_effect=Exception('state mismatch'),
        ):
            response = kc_client.get(
                '/auth/keycloak/callback?code=x&state=y', follow_redirects=True
            )

        assert b'Keycloak sign-in failed' in response.data
        with kc_client.session_transaction() as sess:
            assert 'user' not in sess

    def test_logout_clears_tokens(self, kc_client):
        with kc_client.session_transaction() as sess:
            sess['user'] = {
                'username': 'alice',
                'is_authenticated': True,
                'auth_method': 'keycloak',
            }
            sess['keycloak_tokens'] = {
                'access_token': 'access-abc',
                'id_token': 'id-abc',
            }

        with patch.object(
            keycloak,
            '_server_metadata',
            return_value={
                'end_session_endpoint': (
                    'https://auth.example.org/realms/dataspace'
                    '/protocol/openid-connect/logout'
                )
            },
        ):
            response = kc_client.post('/auth/logout')

        # Redirected onward to Keycloak so its own session ends too.
        assert response.status_code == 302
        assert 'auth.example.org' in response.location
        assert 'id_token_hint=id-abc' in response.location

        with kc_client.session_transaction() as sess:
            assert 'user' not in sess
            assert 'keycloak_tokens' not in sess


class TestProxyForwardedScheme:
    """Redirect URIs must be https:// when behind a TLS-terminating proxy.

    Keycloak matches redirect_uri literally against the client's registered
    URI, so an http:// URI built from an unforwarded scheme is rejected before
    the user ever sees a login screen.
    """

    PROXY_HEADERS = {
        'X-Forwarded-Proto': 'https',
        'X-Forwarded-Host': 'humanitariandataspace.com',
    }

    @staticmethod
    def _probe(app):
        """Add a route echoing the external URLs, reached through the WSGI stack.

        ProxyFix is WSGI middleware, so it only runs for real requests —
        test_request_context() builds an environ directly and skips it.
        """
        @app.route('/_probe_external_urls')
        def _probe_external_urls():
            from flask import url_for
            return {
                'callback': url_for('auth.keycloak_callback', _external=True),
                'index': url_for('main.index', _external=True),
            }

        return app.test_client()

    def test_external_urls_use_forwarded_scheme(self, kc_app):
        response = self._probe(kc_app).get(
            '/_probe_external_urls',
            base_url='http://127.0.0.1:5000',
            headers=self.PROXY_HEADERS,
        )

        assert response.json['callback'] == (
            'https://humanitariandataspace.com/auth/keycloak/callback'
        )
        assert response.json['index'] == 'https://humanitariandataspace.com/'

    def test_authorize_redirect_sends_https_redirect_uri(self, kc_app, kc_client):
        """End to end: the redirect_uri handed to Keycloak is the https one."""
        with patch.object(
            keycloak, '_server_metadata', return_value={}
        ), responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                'https://auth.example.org/realms/dataspace/.well-known/openid-configuration',
                json={
                    'issuer': 'https://auth.example.org/realms/dataspace',
                    'authorization_endpoint': (
                        'https://auth.example.org/realms/dataspace'
                        '/protocol/openid-connect/auth'
                    ),
                    'token_endpoint': TOKEN_ENDPOINT,
                },
            )
            response = kc_client.get(
                '/auth/keycloak/login',
                base_url='http://127.0.0.1:5000',
                headers=self.PROXY_HEADERS,
            )

        assert response.status_code == 302
        assert quote_plus(
            'https://humanitariandataspace.com/auth/keycloak/callback'
        ) in response.location
        assert quote_plus('http://humanitariandataspace.com') not in response.location

    def test_no_forwarded_headers_leaves_scheme_alone(self, kc_app):
        """Plain local development is unaffected."""
        response = self._probe(kc_app).get(
            '/_probe_external_urls', base_url='http://127.0.0.1:5000'
        )
        assert response.json['index'] == 'http://127.0.0.1:5000/'


class TestForceHttps:
    """FORCE_HTTPS pins the scheme without relying on the proxy's headers."""

    @pytest.fixture
    def https_app(self):
        return create_app(dict(KEYCLOAK_CONFIG, FORCE_HTTPS=True))

    def test_external_urls_are_https_without_any_headers(self, https_app):
        """The point of the flag: no X-Forwarded-Proto needed."""
        response = TestProxyForwardedScheme._probe(https_app).get(
            '/_probe_external_urls', base_url='http://humanitariandataspace.com'
        )

        assert response.json['callback'] == (
            'https://humanitariandataspace.com/auth/keycloak/callback'
        )
        assert response.json['index'] == 'https://humanitariandataspace.com/'

    def test_forced_scheme_beats_contradicting_forwarded_header(self, https_app):
        """A proxy sending X-Forwarded-Proto: http cannot downgrade the URL."""
        response = TestProxyForwardedScheme._probe(https_app).get(
            '/_probe_external_urls',
            base_url='http://humanitariandataspace.com',
            headers={'X-Forwarded-Proto': 'http'},
        )

        assert response.json['callback'].startswith('https://')

    def test_authorize_redirect_uses_https(self, https_app):
        """End to end: Keycloak receives the https redirect_uri it expects."""
        with patch.object(
            keycloak, '_server_metadata', return_value={}
        ), responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                'https://auth.example.org/realms/dataspace/.well-known/openid-configuration',
                json={
                    'issuer': 'https://auth.example.org/realms/dataspace',
                    'authorization_endpoint': (
                        'https://auth.example.org/realms/dataspace'
                        '/protocol/openid-connect/auth'
                    ),
                    'token_endpoint': TOKEN_ENDPOINT,
                },
            )
            response = https_app.test_client().get(
                '/auth/keycloak/login', base_url='http://humanitariandataspace.com'
            )

        assert response.status_code == 302
        assert quote_plus(
            'https://humanitariandataspace.com/auth/keycloak/callback'
        ) in response.location

    def test_hsts_header_set(self, https_app):
        response = https_app.test_client().get('/')
        assert response.headers['Strict-Transport-Security'] == 'max-age=31536000'
        # Not bound to subdomains — the sandbox host is not covered.
        assert 'includeSubDomains' not in response.headers['Strict-Transport-Security']

    def test_no_hsts_when_disabled(self, kc_app):
        response = kc_app.test_client().get('/')
        assert 'Strict-Transport-Security' not in response.headers


class TestTokenRefresh:
    """get_valid_access_token() renews tokens before they go stale."""

    def test_returns_token_when_fresh(self, kc_app):
        with kc_app.test_request_context():
            from flask import session
            session['keycloak_tokens'] = {
                'access_token': 'still-good',
                'refresh_token': 'r',
                'expires_at': time.time() + 3600,
            }
            assert keycloak.get_valid_access_token() == 'still-good'

    def test_returns_none_without_token(self, kc_app):
        with kc_app.test_request_context():
            assert keycloak.get_valid_access_token() is None

    def test_returns_token_when_expiry_unknown(self, kc_app):
        with kc_app.test_request_context():
            from flask import session
            session['keycloak_tokens'] = {'access_token': 'no-expiry'}
            assert keycloak.get_valid_access_token() == 'no-expiry'

    @responses.activate
    def test_refreshes_expired_token(self, kc_app):
        responses.add(
            responses.POST,
            TOKEN_ENDPOINT,
            json={
                'access_token': 'fresh-token',
                'refresh_token': 'new-refresh',
                'expires_in': 300,
            },
            status=200,
        )

        with kc_app.test_request_context():
            from flask import session
            session['keycloak_tokens'] = {
                'access_token': 'stale',
                'refresh_token': 'old-refresh',
                'expires_at': time.time() - 1,
            }

            with patch.object(
                keycloak, '_server_metadata', return_value={'token_endpoint': TOKEN_ENDPOINT}
            ):
                assert keycloak.get_valid_access_token() == 'fresh-token'

            assert session['keycloak_tokens']['refresh_token'] == 'new-refresh'
            assert session['keycloak_tokens']['expires_at'] > time.time()

    @responses.activate
    def test_refresh_failure_clears_tokens(self, kc_app):
        responses.add(
            responses.POST, TOKEN_ENDPOINT, json={'error': 'invalid_grant'}, status=400
        )

        with kc_app.test_request_context():
            from flask import session
            session['keycloak_tokens'] = {
                'access_token': 'stale',
                'refresh_token': 'revoked',
                'expires_at': time.time() - 1,
            }

            with patch.object(
                keycloak, '_server_metadata', return_value={'token_endpoint': TOKEN_ENDPOINT}
            ):
                assert keycloak.get_valid_access_token() is None

            assert 'keycloak_tokens' not in session

    def test_expired_without_refresh_token_clears(self, kc_app):
        with kc_app.test_request_context():
            from flask import session
            session['keycloak_tokens'] = {
                'access_token': 'stale',
                'expires_at': time.time() - 1,
            }
            assert keycloak.get_valid_access_token() is None
            assert 'keycloak_tokens' not in session

    def test_has_session_token_does_not_refresh(self, kc_app):
        """The display-path check never calls out to Keycloak."""
        with kc_app.test_request_context():
            from flask import session
            session['keycloak_tokens'] = {
                'access_token': 'stale',
                'refresh_token': 'r',
                'expires_at': time.time() - 1,
            }
            # No responses mock registered: a network call would raise.
            assert keycloak.has_session_token() is True


class TestBearerTokenQueries:
    """SPARQLClient sends the access token as a bearer token."""

    @responses.activate
    def test_sends_bearer_header(self):
        responses.add(
            responses.POST,
            'https://endpoint.example.org/sparql',
            json={'head': {'vars': ['s']}, 'results': {'bindings': []}},
            status=200,
        )

        creds = EndpointCredentials(
            fdp_uri='https://fdp.example.org',
            sparql_endpoint='https://endpoint.example.org/sparql',
            username='',
            password='',
            access_token='access-abc',
        )
        SPARQLClient().execute_query(
            'https://endpoint.example.org/sparql', 'SELECT * WHERE { ?s ?p ?o }', creds
        )

        assert responses.calls[0].request.headers['Authorization'] == 'Bearer access-abc'

    @responses.activate
    def test_bearer_takes_precedence_over_basic(self):
        """A token-bearing credential must not also leak the password."""
        responses.add(
            responses.POST,
            'https://endpoint.example.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
            status=200,
        )

        creds = EndpointCredentials(
            fdp_uri='https://fdp.example.org',
            sparql_endpoint='https://endpoint.example.org/sparql',
            username='basicuser',
            password='basicpass',
            access_token='access-abc',
        )
        SPARQLClient().execute_query(
            'https://endpoint.example.org/sparql', 'SELECT * WHERE { ?s ?p ?o }', creds
        )

        auth_header = responses.calls[0].request.headers['Authorization']
        assert auth_header == 'Bearer access-abc'
        assert 'Basic' not in auth_header

    @responses.activate
    def test_basic_auth_unchanged_without_token(self):
        """Endpoints still on HTTP Basic keep working exactly as before."""
        responses.add(
            responses.POST,
            'https://endpoint.example.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
            status=200,
        )

        creds = EndpointCredentials(
            fdp_uri='https://fdp.example.org',
            sparql_endpoint='https://endpoint.example.org/sparql',
            username='basicuser',
            password='basicpass',
        )
        SPARQLClient().execute_query(
            'https://endpoint.example.org/sparql', 'SELECT * WHERE { ?s ?p ?o }', creds
        )

        assert responses.calls[0].request.headers['Authorization'].startswith('Basic ')

    @responses.activate
    def test_federated_query_sends_token_to_each_endpoint(self):
        for host in ('one', 'two'):
            responses.add(
                responses.POST,
                f'https://{host}.example.org/sparql',
                json={'head': {'vars': []}, 'results': {'bindings': []}},
                status=200,
            )

        endpoints = [
            'https://one.example.org/sparql',
            'https://two.example.org/sparql',
        ]
        creds_map = {
            url: EndpointCredentials(
                fdp_uri='', sparql_endpoint=url, username='', password='',
                access_token='access-abc',
            )
            for url in endpoints
        }

        result = SPARQLClient().execute_federated(
            SPARQLQuery(query_text='SELECT * WHERE { ?s ?p ?o }', target_endpoints=endpoints),
            creds_map,
            {},
        )

        assert result.successful_endpoints == 2
        for call in responses.calls:
            assert call.request.headers['Authorization'] == 'Bearer access-abc'


class TestQueryRouteCredentialResolution:
    """The /sparql/query route picks the right credential per endpoint."""

    ENDPOINT = {
        'endpoint_url': 'https://one.example.org/sparql',
        'dataset_uri': 'https://example.org/dataset/1',
        'dataset_title': 'Test Dataset',
        'fdp_uri': 'https://example.org',
        'fdp_title': 'Test FDP',
        'catalog_title': 'Test Catalog',
    }

    def _sign_in_with_keycloak(self, client, extra_credentials=None):
        with client.session_transaction() as sess:
            sess['user'] = {
                'username': 'alice',
                'password': '',
                'is_authenticated': True,
                'auth_method': 'keycloak',
            }
            sess['keycloak_tokens'] = {
                'access_token': 'access-abc',
                'refresh_token': 'r',
                'expires_at': time.time() + 3600,
            }
            sess['discovered_endpoints'] = {'hash1': self.ENDPOINT}
            sess['selection'] = [{'uri': self.ENDPOINT['dataset_uri']}]
            sess['endpoint_credentials'] = extra_credentials or {}

    @responses.activate
    def test_token_used_for_endpoint_without_saved_credentials(self, kc_client):
        responses.add(
            responses.POST,
            self.ENDPOINT['endpoint_url'],
            json={'head': {'vars': []}, 'results': {'bindings': []}},
            status=200,
        )
        self._sign_in_with_keycloak(kc_client)

        kc_client.post('/sparql/query', data={
            'query': 'SELECT * WHERE { ?s ?p ?o }',
            'endpoints': ['hash1'],
        })

        assert responses.calls[0].request.headers['Authorization'] == 'Bearer access-abc'

    @responses.activate
    def test_saved_credentials_win_over_token(self, kc_client):
        """A provider still on Basic keeps its per-endpoint credentials."""
        responses.add(
            responses.POST,
            self.ENDPOINT['endpoint_url'],
            json={'head': {'vars': []}, 'results': {'bindings': []}},
            status=200,
        )
        self._sign_in_with_keycloak(kc_client, extra_credentials={
            'hash1': {
                'fdp_uri': 'https://example.org',
                'sparql_endpoint': self.ENDPOINT['endpoint_url'],
                'username': 'dbuser',
                'password': 'dbpass',
            }
        })

        kc_client.post('/sparql/query', data={
            'query': 'SELECT * WHERE { ?s ?p ?o }',
            'endpoints': ['hash1'],
        })

        assert responses.calls[0].request.headers['Authorization'].startswith('Basic ')

    def test_expired_keycloak_session_redirects_to_login(self, kc_client):
        """An unrefreshable token sends the user back to sign in, not to a 401."""
        with kc_client.session_transaction() as sess:
            sess['user'] = {
                'username': 'alice',
                'password': '',
                'is_authenticated': True,
                'auth_method': 'keycloak',
            }
            # Expired with no refresh token — unrecoverable.
            sess['keycloak_tokens'] = {
                'access_token': 'stale',
                'expires_at': time.time() - 1,
            }
            sess['discovered_endpoints'] = {'hash1': self.ENDPOINT}
            sess['selection'] = [{'uri': self.ENDPOINT['dataset_uri']}]
            sess['endpoint_credentials'] = {}

        response = kc_client.post('/sparql/query', data={
            'query': 'SELECT * WHERE { ?s ?p ?o }',
            'endpoints': ['hash1'],
        }, follow_redirects=True)

        assert b'Keycloak session has expired' in response.data

    @responses.activate
    def test_password_login_still_uses_basic(self, kc_client):
        """Keycloak being available does not change the password login path."""
        responses.add(
            responses.POST,
            self.ENDPOINT['endpoint_url'],
            json={'head': {'vars': []}, 'results': {'bindings': []}},
            status=200,
        )
        with kc_client.session_transaction() as sess:
            sess['user'] = {
                'username': 'bob',
                'password': 'bobpass',
                'is_authenticated': True,
                'auth_method': 'password',
            }
            sess['discovered_endpoints'] = {'hash1': self.ENDPOINT}
            sess['selection'] = [{'uri': self.ENDPOINT['dataset_uri']}]
            sess['endpoint_credentials'] = {}

        kc_client.post('/sparql/query', data={
            'query': 'SELECT * WHERE { ?s ?p ?o }',
            'endpoints': ['hash1'],
        })

        assert responses.calls[0].request.headers['Authorization'].startswith('Basic ')
