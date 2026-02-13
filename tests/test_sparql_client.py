"""Tests for the SPARQL Client."""

import pytest
import responses
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError

from app.services.sparql_client import (
    SPARQLClient,
    SPARQLConnectionError,
    SPARQLAuthError,
    SPARQLQueryError,
)
from app.models import SPARQLQuery, EndpointCredentials


class TestSPARQLClientExecuteQuery:
    """Tests for SPARQLClient.execute_query()."""

    @responses.activate
    def test_execute_query_success(self):
        """Test successful query execution."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            json={
                'head': {'vars': ['s', 'p', 'o']},
                'results': {
                    'bindings': [
                        {
                            's': {'type': 'uri', 'value': 'http://example.org/1'},
                            'p': {'type': 'uri', 'value': 'http://example.org/pred'},
                            'o': {'type': 'literal', 'value': 'test'},
                        },
                    ]
                }
            },
            content_type='application/sparql-results+json',
        )

        client = SPARQLClient()
        result = client.execute_query(
            'https://example.org/sparql',
            'SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1'
        )

        assert 'bindings' in result
        assert 'variables' in result
        assert result['variables'] == ['s', 'p', 'o']
        assert len(result['bindings']) == 1
        assert result['bindings'][0]['s']['value'] == 'http://example.org/1'

    @responses.activate
    def test_execute_query_with_auth(self):
        """Test query with authentication."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
        )

        client = SPARQLClient()
        creds = EndpointCredentials(
            fdp_uri='http://fdp.example.org',
            sparql_endpoint='https://example.org/sparql',
            username='user',
            password='pass',
        )

        result = client.execute_query(
            'https://example.org/sparql',
            'SELECT * WHERE { ?s ?p ?o }',
            creds
        )

        assert result is not None
        # Check that auth header was sent
        assert responses.calls[0].request.headers.get('Authorization') is not None

    @responses.activate
    def test_execute_query_without_auth_when_no_username(self):
        """Test that auth is not sent when username is empty."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
        )

        client = SPARQLClient()
        creds = EndpointCredentials(
            fdp_uri='http://fdp.example.org',
            sparql_endpoint='https://example.org/sparql',
            username='',
            password='',
        )

        result = client.execute_query(
            'https://example.org/sparql',
            'SELECT * WHERE { ?s ?p ?o }',
            creds
        )

        assert result is not None
        # No auth header when username is empty
        assert responses.calls[0].request.headers.get('Authorization') is None

    @responses.activate
    def test_execute_query_auth_error_401(self):
        """Test handling of authentication failure (401)."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            status=401,
        )

        client = SPARQLClient()
        with pytest.raises(SPARQLAuthError) as exc_info:
            client.execute_query(
                'https://example.org/sparql',
                'SELECT * WHERE { ?s ?p ?o }'
            )

        assert 'Authentication failed' in str(exc_info.value)

    @responses.activate
    def test_execute_query_auth_error_403(self):
        """Test handling of access denied (403)."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            status=403,
        )

        client = SPARQLClient()
        with pytest.raises(SPARQLAuthError) as exc_info:
            client.execute_query(
                'https://example.org/sparql',
                'SELECT * WHERE { ?s ?p ?o }'
            )

        assert 'Access denied' in str(exc_info.value)

    @responses.activate
    def test_execute_query_connection_error(self):
        """Test handling of connection errors."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            body=RequestsConnectionError("Connection refused"),
        )

        client = SPARQLClient()
        with pytest.raises(SPARQLConnectionError) as exc_info:
            client.execute_query(
                'https://example.org/sparql',
                'SELECT * WHERE { ?s ?p ?o }'
            )

        assert 'Could not connect' in str(exc_info.value)

    @responses.activate
    def test_execute_query_timeout(self):
        """Test handling of timeout."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            body=Timeout("Request timed out"),
        )

        client = SPARQLClient(timeout=5)
        with pytest.raises(SPARQLConnectionError) as exc_info:
            client.execute_query(
                'https://example.org/sparql',
                'SELECT * WHERE { ?s ?p ?o }'
            )

        assert 'timed out' in str(exc_info.value)

    @responses.activate
    def test_execute_query_syntax_error(self):
        """Test handling of query syntax error (400)."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            body='Syntax error at line 1',
            status=400,
        )

        client = SPARQLClient()
        with pytest.raises(SPARQLQueryError) as exc_info:
            client.execute_query(
                'https://example.org/sparql',
                'INVALID QUERY'
            )

        assert 'Query syntax error' in str(exc_info.value)

    @responses.activate
    def test_execute_query_empty_results(self):
        """Test handling of empty results."""
        responses.add(
            responses.POST,
            'https://example.org/sparql',
            json={'head': {'vars': ['x']}, 'results': {'bindings': []}},
        )

        client = SPARQLClient()
        result = client.execute_query(
            'https://example.org/sparql',
            'SELECT ?x WHERE { ?x a <http://example.org/Nothing> }'
        )

        assert result['variables'] == ['x']
        assert result['bindings'] == []


class TestSPARQLClientFederated:
    """Tests for federated query execution."""

    @responses.activate
    def test_execute_federated_all_success(self):
        """Test federated query with all endpoints succeeding."""
        responses.add(
            responses.POST,
            'https://endpoint1.org/sparql',
            json={
                'head': {'vars': ['x']},
                'results': {'bindings': [{'x': {'value': '1'}}]}
            },
        )
        responses.add(
            responses.POST,
            'https://endpoint2.org/sparql',
            json={
                'head': {'vars': ['x']},
                'results': {'bindings': [{'x': {'value': '2'}}]}
            },
        )

        client = SPARQLClient()
        query = SPARQLQuery(
            query_text='SELECT ?x WHERE { ?x ?p ?o }',
            target_endpoints=[
                'https://endpoint1.org/sparql',
                'https://endpoint2.org/sparql'
            ],
        )

        result = client.execute_federated(
            query,
            credentials_map={},
            fdp_titles={
                'https://endpoint1.org/sparql': 'FDP 1',
                'https://endpoint2.org/sparql': 'FDP 2',
            }
        )

        assert result.successful_endpoints == 2
        assert result.failed_endpoints == 0
        assert result.total_bindings == 2
        assert len(result.endpoint_results) == 2

    @responses.activate
    def test_execute_federated_partial_failure(self):
        """Test federated query with one endpoint failing."""
        responses.add(
            responses.POST,
            'https://endpoint1.org/sparql',
            json={'head': {'vars': ['x']}, 'results': {'bindings': []}},
        )
        responses.add(
            responses.POST,
            'https://endpoint2.org/sparql',
            status=500,
        )

        client = SPARQLClient()
        query = SPARQLQuery(
            query_text='SELECT ?x WHERE { ?x ?p ?o }',
            target_endpoints=[
                'https://endpoint1.org/sparql',
                'https://endpoint2.org/sparql'
            ],
        )

        result = client.execute_federated(query, {}, {})

        assert result.successful_endpoints == 1
        assert result.failed_endpoints == 1

        # Find the failed result
        failed = [r for r in result.endpoint_results if not r.success]
        assert len(failed) == 1
        assert failed[0].error_message is not None

    @responses.activate
    def test_execute_federated_with_credentials(self):
        """Test federated query with credentials for some endpoints."""
        responses.add(
            responses.POST,
            'https://endpoint1.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
        )
        responses.add(
            responses.POST,
            'https://endpoint2.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
        )

        client = SPARQLClient()
        query = SPARQLQuery(
            query_text='SELECT ?x WHERE { ?x ?p ?o }',
            target_endpoints=[
                'https://endpoint1.org/sparql',
                'https://endpoint2.org/sparql'
            ],
        )

        credentials_map = {
            'https://endpoint1.org/sparql': EndpointCredentials(
                fdp_uri='http://fdp1.org',
                sparql_endpoint='https://endpoint1.org/sparql',
                username='user1',
                password='pass1',
            )
        }

        result = client.execute_federated(query, credentials_map, {})

        assert result.successful_endpoints == 2
        # First request should have auth
        assert responses.calls[0].request.headers.get('Authorization') is not None
        # Second request should not have auth
        assert responses.calls[1].request.headers.get('Authorization') is None

    @responses.activate
    def test_execute_federated_records_execution_time(self):
        """Test that execution time is recorded for each endpoint."""
        responses.add(
            responses.POST,
            'https://endpoint1.org/sparql',
            json={'head': {'vars': []}, 'results': {'bindings': []}},
        )

        client = SPARQLClient()
        query = SPARQLQuery(
            query_text='SELECT ?x WHERE { ?x ?p ?o }',
            target_endpoints=['https://endpoint1.org/sparql'],
        )

        result = client.execute_federated(query, {}, {})

        assert len(result.endpoint_results) == 1
        assert result.endpoint_results[0].execution_time_ms >= 0


class TestSPARQLClientValidation:
    """Tests for query validation."""

    def test_validate_select_query(self):
        """Test validation of SELECT query."""
        client = SPARQLClient()
        assert client.validate_query('SELECT ?s WHERE { ?s ?p ?o }') is True

    def test_validate_construct_query(self):
        """Test validation of CONSTRUCT query."""
        client = SPARQLClient()
        assert client.validate_query('CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }') is True

    def test_validate_ask_query(self):
        """Test validation of ASK query."""
        client = SPARQLClient()
        assert client.validate_query('ASK WHERE { ?s ?p ?o }') is True

    def test_validate_describe_query(self):
        """Test validation of DESCRIBE query."""
        client = SPARQLClient()
        assert client.validate_query('DESCRIBE <http://example.org/resource>') is True

    def test_validate_invalid_query(self):
        """Test validation of invalid query."""
        client = SPARQLClient()
        assert client.validate_query('DELETE WHERE { ?s ?p ?o }') is False

    def test_validate_query_with_prefix(self):
        """Test validation of query with PREFIX."""
        client = SPARQLClient()
        query = '''PREFIX ex: <http://example.org/>
SELECT * WHERE { ?s ?p ?o }'''
        assert client.validate_query(query) is True

    def test_validate_empty_query(self):
        """Test validation of empty query."""
        client = SPARQLClient()
        assert client.validate_query('') is False
        assert client.validate_query('   ') is False

    def test_validate_query_case_insensitive(self):
        """Test that validation is case-insensitive."""
        client = SPARQLClient()
        assert client.validate_query('select ?s where { ?s ?p ?o }') is True
        assert client.validate_query('Select ?s Where { ?s ?p ?o }') is True
