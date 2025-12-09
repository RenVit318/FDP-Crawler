"""Data models for Data Access Requests."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class DatasetReference:
    """Minimal dataset info for request composition."""

    uri: str
    title: str
    contact_email: str
    fdp_title: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'uri': self.uri,
            'title': self.title,
            'contact_email': self.contact_email,
            'fdp_title': self.fdp_title,
        }


@dataclass
class DataRequest:
    """A data access request being composed."""

    requester_name: str
    requester_email: str
    requester_affiliation: str
    datasets: List[DatasetReference]
    query: str
    purpose: str
    requester_orcid: Optional[str] = None
    output_constraints: Optional[str] = None
    timeline: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'requester_name': self.requester_name,
            'requester_email': self.requester_email,
            'requester_affiliation': self.requester_affiliation,
            'requester_orcid': self.requester_orcid,
            'datasets': [ds.to_dict() for ds in self.datasets],
            'query': self.query,
            'purpose': self.purpose,
            'output_constraints': self.output_constraints,
            'timeline': self.timeline,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class ComposedEmail:
    """A composed email ready for sending/display."""

    recipients: List[str]
    subject: str
    body: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'recipients': self.recipients,
            'subject': self.subject,
            'body': self.body,
        }
