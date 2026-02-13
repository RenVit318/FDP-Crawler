"""Tests for authentication functionality."""

import pytest


class TestLoginLogout:
    """Tests for login and logout."""

    def test_login_page_loads(self, client):
        """Test login page loads."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Login' in response.data
        assert b'Username' in response.data
        assert b'Password' in response.data

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Welcome' in response.data

        with client.session_transaction() as sess:
            assert sess['user']['username'] == 'testuser'
            assert sess['user']['is_authenticated'] is True

    def test_login_empty_username(self, client):
        """Test login with empty username."""
        response = client.post('/auth/login', data={
            'username': '',
            'password': 'testpass',
        })

        assert response.status_code == 200
        assert b'Please enter both' in response.data

    def test_login_empty_password(self, client):
        """Test login with empty password."""
        response = client.post('/auth/login', data={
            'username': 'testuser',
            'password': '',
        })

        assert response.status_code == 200
        assert b'Please enter both' in response.data

    def test_login_redirects_if_already_logged_in(self, client):
        """Test that login page redirects if already logged in."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'testuser', 'is_authenticated': True}

        response = client.get('/auth/login')
        assert response.status_code == 302  # Redirect

    def test_login_redirect_to_next(self, client):
        """Test login redirects to next parameter."""
        response = client.post('/auth/login?next=/sparql/', data={
            'username': 'testuser',
            'password': 'testpass',
        })

        assert response.status_code == 302
        assert '/sparql/' in response.location

    def test_login_ignores_external_next(self, client):
        """Test that login ignores external next URLs."""
        response = client.post('/auth/login?next=http://evil.com', data={
            'username': 'testuser',
            'password': 'testpass',
        })

        assert response.status_code == 302
        # Should redirect to home, not external URL
        assert 'evil.com' not in response.location

    def test_logout(self, client):
        """Test logout."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'testuser', 'is_authenticated': True}
            sess['endpoint_credentials'] = {'hash1': {'sparql_endpoint': 'http://example.org'}}
            sess['query_result'] = {'query': 'test'}

        response = client.post('/auth/logout', follow_redirects=True)
        assert response.status_code == 200
        assert b'Goodbye' in response.data

        with client.session_transaction() as sess:
            assert 'user' not in sess
            # endpoint_credentials is re-initialized by before_request, but should be empty
            assert sess.get('endpoint_credentials', {}) == {}
            assert 'query_result' not in sess


class TestLoginRequired:
    """Tests for login_required decorator."""

    def test_credentials_requires_login(self, client):
        """Test credentials page requires login."""
        response = client.get('/auth/credentials', follow_redirects=True)
        assert b'Please log in' in response.data

    def test_credentials_accessible_when_logged_in(self, client):
        """Test credentials page accessible when logged in."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {}

        response = client.get('/auth/credentials')
        assert response.status_code == 200
        assert b'Endpoint Credentials' in response.data


class TestCredentialsManagement:
    """Tests for endpoint credentials management."""

    def test_list_credentials_no_fdps(self, client):
        """Test listing credentials when no FDPs configured."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {}

        response = client.get('/auth/credentials')
        assert response.status_code == 200
        assert b'No FDPs Configured' in response.data

    def test_list_credentials_with_fdps(self, client):
        """Test listing credentials with FDPs."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {
                'hash1': {'uri': 'http://example.org', 'title': 'Test FDP'}
            }
            sess['endpoint_credentials'] = {}

        response = client.get('/auth/credentials')
        assert response.status_code == 200
        assert b'Test FDP' in response.data
        assert b'Without Endpoints' in response.data

    def test_list_credentials_shows_configured(self, client):
        """Test that configured credentials are shown."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {
                'hash1': {'uri': 'http://example.org', 'title': 'Test FDP'}
            }
            sess['endpoint_credentials'] = {
                'hash1': {
                    'sparql_endpoint': 'http://example.org/sparql',
                    'username': 'dbuser',
                    'password': 'dbpass',
                }
            }

        response = client.get('/auth/credentials')
        assert response.status_code == 200
        assert b'Configured Endpoints' in response.data
        assert b'http://example.org/sparql' in response.data

    def test_configure_credentials_page_loads(self, client):
        """Test configure credentials page loads."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {
                'hash1': {'uri': 'http://example.org', 'title': 'Test FDP'}
            }

        response = client.get('/auth/credentials/hash1')
        assert response.status_code == 200
        assert b'Configure SPARQL Credentials' in response.data
        assert b'Test FDP' in response.data

    def test_configure_credentials_fdp_not_found(self, client):
        """Test configure credentials with invalid FDP hash."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {}

        response = client.get('/auth/credentials/nonexistent', follow_redirects=True)
        assert b'FDP not found' in response.data

    def test_configure_credentials_save(self, client):
        """Test saving credentials."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {
                'hash1': {'uri': 'http://example.org', 'title': 'Test FDP'}
            }

        response = client.post('/auth/credentials/hash1', data={
            'sparql_endpoint': 'http://example.org/sparql',
            'username': 'dbuser',
            'password': 'dbpass',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Credentials saved' in response.data

        with client.session_transaction() as sess:
            assert 'hash1' in sess['endpoint_credentials']
            creds = sess['endpoint_credentials']['hash1']
            assert creds['sparql_endpoint'] == 'http://example.org/sparql'
            assert creds['username'] == 'dbuser'
            assert creds['password'] == 'dbpass'

    def test_configure_credentials_missing_endpoint(self, client):
        """Test saving credentials without endpoint URL."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {
                'hash1': {'uri': 'http://example.org', 'title': 'Test FDP'}
            }

        response = client.post('/auth/credentials/hash1', data={
            'sparql_endpoint': '',
            'username': 'dbuser',
            'password': 'dbpass',
        })

        assert response.status_code == 200
        assert b'SPARQL endpoint URL is required' in response.data

    def test_configure_credentials_preserves_password(self, client):
        """Test that existing password is preserved if not provided."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {
                'hash1': {'uri': 'http://example.org', 'title': 'Test FDP'}
            }
            sess['endpoint_credentials'] = {
                'hash1': {
                    'fdp_uri': 'http://example.org',
                    'sparql_endpoint': 'http://example.org/sparql',
                    'username': 'olduser',
                    'password': 'oldpass',
                }
            }

        response = client.post('/auth/credentials/hash1', data={
            'sparql_endpoint': 'http://example.org/new-sparql',
            'username': 'newuser',
            'password': '',  # Empty password
        }, follow_redirects=True)

        assert response.status_code == 200

        with client.session_transaction() as sess:
            creds = sess['endpoint_credentials']['hash1']
            assert creds['sparql_endpoint'] == 'http://example.org/new-sparql'
            assert creds['username'] == 'newuser'
            assert creds['password'] == 'oldpass'  # Preserved

    def test_remove_credentials(self, client):
        """Test removing credentials."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['fdps'] = {
                'hash1': {'uri': 'http://example.org', 'title': 'Test FDP'}
            }
            sess['endpoint_credentials'] = {
                'hash1': {'sparql_endpoint': 'http://example.org/sparql'}
            }

        response = client.post('/auth/credentials/hash1/remove', follow_redirects=True)
        assert response.status_code == 200
        assert b'Credentials removed' in response.data

        with client.session_transaction() as sess:
            assert 'hash1' not in sess['endpoint_credentials']

    def test_remove_credentials_not_found(self, client):
        """Test removing credentials that don't exist."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'is_authenticated': True}
            sess['endpoint_credentials'] = {}

        response = client.post('/auth/credentials/nonexistent/remove', follow_redirects=True)
        assert b'No credentials found' in response.data
