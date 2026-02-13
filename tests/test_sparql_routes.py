"""Tests for SPARQL routes."""

import hashlib

import pytest
import responses


def _ep_hash(url: str) -> str:
    """Generate the same MD5 hash used by the application."""
    return hashlib.md5(url.encode()).hexdigest()


# Reusable session helpers

def _session_with_basket_and_endpoints(sess, username='test', password='testpass'):
    """Set up a session with a logged-in user, a basket dataset, and a discovered endpoint."""
    ep_url = 'http://example.org/sparql'
    dataset_uri = 'http://example.org/dataset/1'
    ep_hash = _ep_hash(ep_url)

    sess['user'] = {
        'username': username,
        'password': password,
        'is_authenticated': True,
    }
    sess['basket'] = [
        {'uri': dataset_uri, 'title': 'Test Dataset', 'fdp_title': 'Test FDP'},
    ]
    sess['discovered_endpoints'] = {
        ep_hash: {
            'endpoint_url': ep_url,
            'dataset_uri': dataset_uri,
            'dataset_title': 'Test Dataset',
            'fdp_uri': 'http://example.org',
            'fdp_title': 'Test FDP',
            'distribution_title': 'SPARQL endpoint',
        }
    }
    return ep_hash


class TestSPARQLIndex:
    """Tests for SPARQL index page."""

    def test_sparql_index_requires_login(self, client):
        """Test SPARQL index requires login."""
        response = client.get('/sparql/', follow_redirects=True)
        assert b'Please log in' in response.data

    def test_sparql_index_empty_basket(self, client):
        """Test SPARQL index with empty basket."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            sess['basket'] = []
            sess['discovered_endpoints'] = {}

        response = client.get('/sparql/')
        assert response.status_code == 200
        assert b'Basket is Empty' in response.data

    def test_sparql_index_basket_no_endpoints(self, client):
        """Test SPARQL index with basket datasets but no discovered endpoints."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            sess['basket'] = [
                {'uri': 'http://example.org/dataset/1', 'title': 'Test Dataset', 'fdp_title': 'Test FDP'},
            ]
            sess['discovered_endpoints'] = {}

        response = client.get('/sparql/')
        assert response.status_code == 200
        assert b'No SPARQL Endpoints Found' in response.data

    def test_sparql_index_with_endpoints(self, client):
        """Test SPARQL index shows endpoints from basket datasets."""
        with client.session_transaction() as sess:
            _session_with_basket_and_endpoints(sess)

        response = client.get('/sparql/')
        assert response.status_code == 200
        assert b'Available Endpoints' in response.data
        assert b'Test FDP' in response.data
        assert b'http://example.org/sparql' in response.data

    def test_sparql_index_filters_by_basket(self, client):
        """Test that endpoints not in basket are excluded."""
        ep_url = 'http://other.org/sparql'
        ep_hash = _ep_hash(ep_url)

        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            # Basket has one dataset, but discovered endpoint belongs to a different dataset
            sess['basket'] = [
                {'uri': 'http://example.org/dataset/1', 'title': 'In Basket'},
            ]
            sess['discovered_endpoints'] = {
                ep_hash: {
                    'endpoint_url': ep_url,
                    'dataset_uri': 'http://other.org/dataset/99',  # Not in basket
                    'dataset_title': 'Other Dataset',
                    'fdp_uri': 'http://other.org',
                    'fdp_title': 'Other FDP',
                }
            }

        response = client.get('/sparql/')
        assert response.status_code == 200
        # No matching endpoints, so should show "no endpoints" state
        assert b'No SPARQL Endpoints Found' in response.data


class TestSPARQLQuery:
    """Tests for SPARQL query page."""

    def test_query_requires_login(self, client):
        """Test query page requires login."""
        response = client.get('/sparql/query', follow_redirects=True)
        assert b'Please log in' in response.data

    def test_query_redirects_empty_basket(self, client):
        """Test query page redirects when basket is empty."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            sess['basket'] = []
            sess['discovered_endpoints'] = {}

        response = client.get('/sparql/query', follow_redirects=True)
        assert b'basket is empty' in response.data.lower() or b'Browse' in response.data

    def test_query_redirects_no_endpoints(self, client):
        """Test query page redirects when basket has no endpoints."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            sess['basket'] = [
                {'uri': 'http://example.org/dataset/1', 'title': 'Test Dataset'},
            ]
            sess['discovered_endpoints'] = {}

        response = client.get('/sparql/query', follow_redirects=True)
        assert b'No SPARQL endpoints' in response.data

    def test_query_page_loads(self, client):
        """Test query page loads with basket endpoints."""
        with client.session_transaction() as sess:
            _session_with_basket_and_endpoints(sess)

        response = client.get('/sparql/query')
        assert response.status_code == 200
        assert b'SPARQL Query Editor' in response.data
        assert b'Test FDP' in response.data

    def test_query_empty_query(self, client):
        """Test submitting empty query."""
        with client.session_transaction() as sess:
            ep_hash = _session_with_basket_and_endpoints(sess)

        response = client.post('/sparql/query', data={
            'query': '',
            'endpoints': [ep_hash],
        })

        assert response.status_code == 200
        assert b'Please enter a SPARQL query' in response.data

    def test_query_no_endpoints_selected(self, client):
        """Test submitting query without selecting endpoints."""
        with client.session_transaction() as sess:
            _session_with_basket_and_endpoints(sess)

        response = client.post('/sparql/query', data={
            'query': 'SELECT * WHERE { ?s ?p ?o }',
            'endpoints': [],
        })

        assert response.status_code == 200
        assert b'Please select at least one endpoint' in response.data

    def test_query_invalid_syntax(self, client):
        """Test submitting invalid query syntax."""
        with client.session_transaction() as sess:
            ep_hash = _session_with_basket_and_endpoints(sess)

        response = client.post('/sparql/query', data={
            'query': 'DELETE WHERE { ?s ?p ?o }',
            'endpoints': [ep_hash],
        })

        assert response.status_code == 200
        assert b'Invalid SPARQL query' in response.data

    @responses.activate
    def test_query_execution(self, client):
        """Test successful query execution."""
        responses.add(
            responses.POST,
            'http://example.org/sparql',
            json={
                'head': {'vars': ['s']},
                'results': {'bindings': [{'s': {'type': 'uri', 'value': 'http://test'}}]}
            },
        )

        with client.session_transaction() as sess:
            ep_hash = _session_with_basket_and_endpoints(sess)

        response = client.post('/sparql/query', data={
            'query': 'SELECT ?s WHERE { ?s ?p ?o }',
            'endpoints': [ep_hash],
        })

        # Should redirect to results
        assert response.status_code == 302
        assert '/sparql/results' in response.location

    @responses.activate
    def test_query_execution_uses_login_credentials(self, client):
        """Test query execution uses login credentials for authentication."""
        responses.add(
            responses.POST,
            'http://example.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
        )

        with client.session_transaction() as sess:
            ep_hash = _session_with_basket_and_endpoints(
                sess, username='dbuser', password='dbpass'
            )

        response = client.post('/sparql/query', data={
            'query': 'SELECT ?s WHERE { ?s ?p ?o }',
            'endpoints': [ep_hash],
        })

        assert response.status_code == 302
        # Verify auth was used (login credentials sent as HTTP Basic Auth)
        assert responses.calls[0].request.headers.get('Authorization') is not None


class TestSPARQLResults:
    """Tests for SPARQL results page."""

    def test_results_requires_login(self, client):
        """Test results page requires login."""
        response = client.get('/sparql/results', follow_redirects=True)
        assert b'Please log in' in response.data

    def test_results_no_data(self, client):
        """Test results page with no stored results."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}

        response = client.get('/sparql/results', follow_redirects=True)
        assert b'No query results' in response.data

    def test_results_displays_data(self, client):
        """Test results page displays stored results."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            sess['query_result'] = {
                'query': {
                    'query_text': 'SELECT ?s WHERE { ?s ?p ?o }',
                    'target_endpoints': ['http://example.org/sparql'],
                    'created_at': '2024-01-01T00:00:00',
                },
                'endpoint_results': [
                    {
                        'endpoint_uri': 'http://example.org/sparql',
                        'fdp_title': 'Test FDP',
                        'success': True,
                        'bindings': [{'s': {'type': 'uri', 'value': 'http://test'}}],
                        'variables': ['s'],
                        'error_message': None,
                        'execution_time_ms': 100,
                    }
                ],
                'total_bindings': 1,
                'successful_endpoints': 1,
                'failed_endpoints': 0,
                'executed_at': '2024-01-01T00:00:00',
            }

        response = client.get('/sparql/results')
        assert response.status_code == 200
        assert b'Query Results' in response.data
        assert b'Test FDP' in response.data
        assert b'http://test' in response.data

    def test_results_displays_errors(self, client):
        """Test results page displays endpoint errors."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            sess['query_result'] = {
                'query': {
                    'query_text': 'SELECT ?s WHERE { ?s ?p ?o }',
                    'target_endpoints': ['http://example.org/sparql'],
                    'created_at': '2024-01-01T00:00:00',
                },
                'endpoint_results': [
                    {
                        'endpoint_uri': 'http://example.org/sparql',
                        'fdp_title': 'Test FDP',
                        'success': False,
                        'bindings': [],
                        'variables': [],
                        'error_message': 'Connection refused',
                        'execution_time_ms': 50,
                    }
                ],
                'total_bindings': 0,
                'successful_endpoints': 0,
                'failed_endpoints': 1,
                'executed_at': '2024-01-01T00:00:00',
            }

        response = client.get('/sparql/results')
        assert response.status_code == 200
        assert b'Failed' in response.data
        assert b'Connection refused' in response.data

    def test_clear_results(self, client):
        """Test clearing query results."""
        with client.session_transaction() as sess:
            sess['user'] = {'username': 'test', 'password': 'pass', 'is_authenticated': True}
            sess['query_result'] = {'query': 'test'}

        response = client.post('/sparql/results/clear', follow_redirects=True)
        assert response.status_code == 200
        assert b'Results cleared' in response.data

        with client.session_transaction() as sess:
            assert 'query_result' not in sess


class TestSPARQLIntegration:
    """Integration tests for SPARQL workflow."""

    @responses.activate
    def test_full_workflow(self, client):
        """Test complete SPARQL query workflow: login -> basket -> query -> results."""
        # Mock the SPARQL endpoint
        responses.add(
            responses.POST,
            'http://example.org/sparql',
            json={
                'head': {'vars': ['count']},
                'results': {'bindings': [{'count': {'type': 'literal', 'value': '42'}}]}
            },
        )

        # Login
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass',
        })

        # Set up basket and discovered endpoints (simulates having browsed dataset details)
        ep_url = 'http://example.org/sparql'
        dataset_uri = 'http://example.org/dataset/1'
        ep_hash = _ep_hash(ep_url)

        with client.session_transaction() as sess:
            sess['basket'] = [
                {'uri': dataset_uri, 'title': 'Test Dataset', 'fdp_title': 'Test FDP'},
            ]
            sess['discovered_endpoints'] = {
                ep_hash: {
                    'endpoint_url': ep_url,
                    'dataset_uri': dataset_uri,
                    'dataset_title': 'Test Dataset',
                    'fdp_uri': 'http://example.org',
                    'fdp_title': 'Test FDP',
                }
            }

        # Execute query
        response = client.post('/sparql/query', data={
            'query': 'SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }',
            'endpoints': [ep_hash],
        })
        assert response.status_code == 302

        # View results
        response = client.get('/sparql/results')
        assert response.status_code == 200
        assert b'42' in response.data

        # Clear results
        response = client.post('/sparql/results/clear', follow_redirects=True)
        assert b'Results cleared' in response.data
