"""Data models for authentication and credentials."""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class EndpointCredentials:
    """SPARQL/AllegroGraph credentials for a specific FDP endpoint.

    Carries either HTTP Basic credentials or an OIDC bearer token; the token
    wins when both are present (see SPARQLClient.execute_query).

    Attributes:
        fdp_uri: The URI of the associated FDP.
        sparql_endpoint: The SPARQL endpoint URL.
        username: Username for authentication.
        password: Password for authentication.
        access_token: OIDC access token (Keycloak) sent as a bearer token.
    """

    fdp_uri: str
    sparql_endpoint: str
    username: str
    password: str
    access_token: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage."""
        return {
            'fdp_uri': self.fdp_uri,
            'sparql_endpoint': self.sparql_endpoint,
            'username': self.username,
            'password': self.password,
            'access_token': self.access_token,
        }
