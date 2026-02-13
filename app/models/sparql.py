"""Data models for SPARQL queries and results."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class SPARQLQuery:
    """Represents a SPARQL query to execute.

    Attributes:
        query_text: The SPARQL query string.
        target_endpoints: List of SPARQL endpoint URIs to query.
        created_at: Timestamp when the query was created.
    """

    query_text: str
    target_endpoints: List[str]
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage.

        Returns:
            Dictionary representation of the query.
        """
        return {
            'query_text': self.query_text,
            'target_endpoints': self.target_endpoints,
            'created_at': self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SPARQLQuery':
        """Create a SPARQLQuery from a dictionary.

        Args:
            data: Dictionary with query fields.

        Returns:
            SPARQLQuery instance.
        """
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            query_text=data['query_text'],
            target_endpoints=data['target_endpoints'],
            created_at=created_at,
        )


@dataclass
class EndpointResult:
    """Results from a single SPARQL endpoint.

    Attributes:
        endpoint_uri: The SPARQL endpoint that was queried.
        fdp_title: Title of the associated FDP.
        success: Whether the query succeeded.
        bindings: List of result bindings (rows).
        variables: List of variable names in the results.
        error_message: Error message if the query failed.
        execution_time_ms: Query execution time in milliseconds.
    """

    endpoint_uri: str
    fdp_title: str
    success: bool
    bindings: List[Dict[str, Any]] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the endpoint result.
        """
        return {
            'endpoint_uri': self.endpoint_uri,
            'fdp_title': self.fdp_title,
            'success': self.success,
            'bindings': self.bindings,
            'variables': self.variables,
            'error_message': self.error_message,
            'execution_time_ms': self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EndpointResult':
        """Create an EndpointResult from a dictionary.

        Args:
            data: Dictionary with result fields.

        Returns:
            EndpointResult instance.
        """
        return cls(
            endpoint_uri=data['endpoint_uri'],
            fdp_title=data['fdp_title'],
            success=data['success'],
            bindings=data.get('bindings', []),
            variables=data.get('variables', []),
            error_message=data.get('error_message'),
            execution_time_ms=data.get('execution_time_ms', 0),
        )


@dataclass
class QueryResult:
    """Aggregated results from federated SPARQL query execution.

    Attributes:
        query: The SPARQLQuery that was executed.
        endpoint_results: List of results from each endpoint.
        total_bindings: Total number of result bindings across all endpoints.
        successful_endpoints: Number of endpoints that succeeded.
        failed_endpoints: Number of endpoints that failed.
        executed_at: Timestamp when the query was executed.
    """

    query: SPARQLQuery
    endpoint_results: List[EndpointResult] = field(default_factory=list)
    total_bindings: int = 0
    successful_endpoints: int = 0
    failed_endpoints: int = 0
    executed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the query result.
        """
        return {
            'query': self.query.to_dict(),
            'endpoint_results': [r.to_dict() for r in self.endpoint_results],
            'total_bindings': self.total_bindings,
            'successful_endpoints': self.successful_endpoints,
            'failed_endpoints': self.failed_endpoints,
            'executed_at': self.executed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueryResult':
        """Create a QueryResult from a dictionary.

        Args:
            data: Dictionary with result fields.

        Returns:
            QueryResult instance.
        """
        executed_at = data.get('executed_at')
        if isinstance(executed_at, str):
            executed_at = datetime.fromisoformat(executed_at)
        elif executed_at is None:
            executed_at = datetime.now()

        return cls(
            query=SPARQLQuery.from_dict(data['query']),
            endpoint_results=[
                EndpointResult.from_dict(r) for r in data.get('endpoint_results', [])
            ],
            total_bindings=data.get('total_bindings', 0),
            successful_endpoints=data.get('successful_endpoints', 0),
            failed_endpoints=data.get('failed_endpoints', 0),
            executed_at=executed_at,
        )
