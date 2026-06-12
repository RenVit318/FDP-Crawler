"""Data models for authentication and credentials."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class EndpointCredentials:
    """SPARQL/AllegroGraph credentials for a specific FDP endpoint.

    Attributes:
        fdp_uri: The URI of the associated FDP.
        sparql_endpoint: The SPARQL endpoint URL.
        username: Username for authentication.
        password: Password for authentication.
    """

    fdp_uri: str
    sparql_endpoint: str
    username: str
    password: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage."""
        return {
            'fdp_uri': self.fdp_uri,
            'sparql_endpoint': self.sparql_endpoint,
            'username': self.username,
            'password': self.password,
        }
