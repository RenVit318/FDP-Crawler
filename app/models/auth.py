"""Data models for authentication and credentials."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class UserSession:
    """Represents a logged-in user session.

    Attributes:
        username: The user's username.
        is_authenticated: Whether the user is authenticated.
    """

    username: str
    is_authenticated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage.

        Returns:
            Dictionary representation of the user session.
        """
        return {
            'username': self.username,
            'is_authenticated': self.is_authenticated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """Create a UserSession from a dictionary.

        Args:
            data: Dictionary with username and is_authenticated keys.

        Returns:
            UserSession instance.
        """
        return cls(
            username=data['username'],
            is_authenticated=data.get('is_authenticated', True),
        )


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
        """Convert to dictionary for session storage.

        Returns:
            Dictionary representation of the credentials.
        """
        return {
            'fdp_uri': self.fdp_uri,
            'sparql_endpoint': self.sparql_endpoint,
            'username': self.username,
            'password': self.password,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EndpointCredentials':
        """Create EndpointCredentials from a dictionary.

        Args:
            data: Dictionary with credential fields.

        Returns:
            EndpointCredentials instance.
        """
        return cls(
            fdp_uri=data['fdp_uri'],
            sparql_endpoint=data['sparql_endpoint'],
            username=data.get('username', ''),
            password=data.get('password', ''),
        )
