"""Data models for the fairdataspace application."""

from app.models.fdp import FairDataPoint
from app.models.dataset import Dataset, ContactPoint, Distribution
from app.models.request import DataRequest, DatasetReference, ComposedEmail
from app.models.auth import EndpointCredentials
from app.models.sparql import SPARQLQuery, EndpointResult, QueryResult

__all__ = [
    'FairDataPoint',
    'Dataset',
    'ContactPoint',
    'Distribution',
    'DataRequest',
    'DatasetReference',
    'ComposedEmail',
    'EndpointCredentials',
    'SPARQLQuery',
    'EndpointResult',
    'QueryResult',
]
