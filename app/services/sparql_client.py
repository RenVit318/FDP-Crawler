"""SPARQL Client for executing authenticated queries against AllegroGraph endpoints."""

import logging
import time
from typing import List, Dict, Any, Optional

import requests
from requests.auth import HTTPBasicAuth

from app.models import SPARQLQuery, EndpointResult, QueryResult, EndpointCredentials


logger = logging.getLogger(__name__)


class SPARQLError(Exception):
    """Base exception for SPARQL-related errors."""

    pass


class SPARQLConnectionError(SPARQLError):
    """Raised when a SPARQL endpoint cannot be reached."""

    pass


class SPARQLAuthError(SPARQLError):
    """Raised when authentication fails."""

    pass


class SPARQLQueryError(SPARQLError):
    """Raised when query execution fails."""

    pass


class SPARQLClient:
    """Client for executing authenticated SPARQL queries against AllegroGraph."""

    def __init__(self, timeout: int = 60):
        """Initialize the SPARQL client.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout

    def execute_query(
        self,
        endpoint_uri: str,
        query: str,
        credentials: Optional[EndpointCredentials] = None,
    ) -> Dict[str, Any]:
        """Execute a SPARQL query against a single endpoint.

        Args:
            endpoint_uri: The SPARQL endpoint URL.
            query: The SPARQL query string.
            credentials: Optional credentials for authentication.

        Returns:
            Dictionary with 'bindings' and 'variables' from query results.

        Raises:
            SPARQLConnectionError: If endpoint is unreachable.
            SPARQLAuthError: If authentication fails.
            SPARQLQueryError: If query execution fails.
        """
        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        auth = None
        if credentials and credentials.username:
            auth = HTTPBasicAuth(credentials.username, credentials.password)

        try:
            response = requests.post(
                endpoint_uri,
                data={'query': query},
                headers=headers,
                auth=auth,
                timeout=self.timeout,
            )

            if response.status_code == 401:
                raise SPARQLAuthError(f"Authentication failed for {endpoint_uri}")

            if response.status_code == 403:
                raise SPARQLAuthError(f"Access denied for {endpoint_uri}")

            response.raise_for_status()

            result = response.json()

            return {
                'bindings': result.get('results', {}).get('bindings', []),
                'variables': result.get('head', {}).get('vars', []),
            }

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout querying {endpoint_uri}: {e}")
            raise SPARQLConnectionError(
                f"Request to {endpoint_uri} timed out"
            ) from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error for {endpoint_uri}: {e}")
            raise SPARQLConnectionError(
                f"Could not connect to {endpoint_uri}"
            ) from e
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                raise SPARQLQueryError(
                    f"Query syntax error: {response.text[:200]}"
                ) from e
            raise SPARQLConnectionError(
                f"HTTP error for {endpoint_uri}: {response.status_code}"
            ) from e
        except ValueError as e:
            raise SPARQLQueryError(
                f"Invalid JSON response from {endpoint_uri}"
            ) from e

    def execute_federated(
        self,
        query: SPARQLQuery,
        credentials_map: Dict[str, EndpointCredentials],
        fdp_titles: Dict[str, str],
    ) -> QueryResult:
        """Execute a SPARQL query across multiple endpoints (client-side federation).

        Args:
            query: The SPARQLQuery to execute.
            credentials_map: Dict mapping endpoint URI to credentials.
            fdp_titles: Dict mapping endpoint URI to FDP title.

        Returns:
            QueryResult with aggregated results from all endpoints.
        """
        endpoint_results: List[EndpointResult] = []
        total_bindings = 0
        successful = 0
        failed = 0

        for endpoint_uri in query.target_endpoints:
            start_time = time.time()
            creds = credentials_map.get(endpoint_uri)
            fdp_title = fdp_titles.get(endpoint_uri, endpoint_uri)

            try:
                result = self.execute_query(endpoint_uri, query.query_text, creds)
                execution_time = int((time.time() - start_time) * 1000)

                endpoint_result = EndpointResult(
                    endpoint_uri=endpoint_uri,
                    fdp_title=fdp_title,
                    success=True,
                    bindings=result['bindings'],
                    variables=result['variables'],
                    execution_time_ms=execution_time,
                )
                total_bindings += len(result['bindings'])
                successful += 1

            except SPARQLError as e:
                execution_time = int((time.time() - start_time) * 1000)
                endpoint_result = EndpointResult(
                    endpoint_uri=endpoint_uri,
                    fdp_title=fdp_title,
                    success=False,
                    error_message=str(e),
                    execution_time_ms=execution_time,
                )
                failed += 1
                logger.warning(f"Query failed for {endpoint_uri}: {e}")

            endpoint_results.append(endpoint_result)

        return QueryResult(
            query=query,
            endpoint_results=endpoint_results,
            total_bindings=total_bindings,
            successful_endpoints=successful,
            failed_endpoints=failed,
        )

    def validate_query(self, query_text: str) -> bool:
        """Validate SPARQL query syntax and reject dangerous operations.

        Args:
            query_text: The SPARQL query to validate.

        Returns:
            True if query appears valid and safe, False otherwise.
        """
        query_stripped = query_text.strip()
        if not query_stripped:
            return False

        # Block dangerous SPARQL UPDATE operations (case-insensitive)
        query_upper = query_stripped.upper()
        dangerous_keywords = [
            'DROP', 'CLEAR', 'INSERT', 'DELETE',
            'LOAD', 'CREATE', 'MOVE', 'COPY', 'ADD',
        ]
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return False

        # Skip PREFIX declarations to find actual query type
        lines = query_stripped.split('\n')
        query_body = ''
        for line in lines:
            line_upper = line.strip().upper()
            if line_upper and not line_upper.startswith('PREFIX'):
                query_body = line_upper
                break

        valid_starts = ('SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE')
        return any(query_body.startswith(s) for s in valid_starts)
