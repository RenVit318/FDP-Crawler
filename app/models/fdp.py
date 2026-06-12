"""Data model for FAIR Data Points."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class FairDataPoint:
    """Represents a FAIR Data Point endpoint."""

    uri: str
    title: str
    description: Optional[str] = None
    publisher: Optional[str] = None
    is_index: bool = False
    catalogs: List[str] = field(default_factory=list)
    linked_fdps: List[str] = field(default_factory=list)
    last_fetched: Optional[datetime] = None
    status: str = 'pending'
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'uri': self.uri,
            'title': self.title,
            'description': self.description,
            'publisher': self.publisher,
            'is_index': self.is_index,
            'catalogs': self.catalogs,
            'linked_fdps': self.linked_fdps,
            'last_fetched': self.last_fetched.isoformat() if self.last_fetched else None,
            'status': self.status,
            'error_message': self.error_message,
        }
