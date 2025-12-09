"""Data models for Datasets and Contact Points."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class ContactPoint:
    """Contact information for data requests."""

    name: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'email': self.email,
            'url': self.url,
        }


@dataclass
class Dataset:
    """Represents a DCAT Dataset with all relevant metadata for discovery."""

    uri: str
    title: str
    catalog_uri: str
    fdp_uri: str
    fdp_title: str
    description: Optional[str] = None
    publisher: Optional[str] = None
    creator: Optional[str] = None
    issued: Optional[datetime] = None
    modified: Optional[datetime] = None
    themes: List[str] = field(default_factory=list)
    theme_labels: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    contact_point: Optional[ContactPoint] = None
    landing_page: Optional[str] = None
    distributions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'uri': self.uri,
            'title': self.title,
            'description': self.description,
            'publisher': self.publisher,
            'creator': self.creator,
            'issued': self.issued.isoformat() if self.issued else None,
            'modified': self.modified.isoformat() if self.modified else None,
            'themes': self.themes,
            'theme_labels': self.theme_labels,
            'keywords': self.keywords,
            'contact_point': self.contact_point.to_dict() if self.contact_point else None,
            'landing_page': self.landing_page,
            'catalog_uri': self.catalog_uri,
            'fdp_uri': self.fdp_uri,
            'fdp_title': self.fdp_title,
            'distributions': self.distributions,
        }
