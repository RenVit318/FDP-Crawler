"""Tests for the FDP Client."""

import pytest
import responses
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError

from app.services.fdp_client import (
    FDPClient,
    FDPError,
    FDPConnectionError,
    FDPParseError,
    FDPTimeoutError,
)


class TestFDPClientFetchFDP:
    """Tests for FDPClient.fetch_fdp()."""

    @responses.activate
    def test_fetch_fdp_success(self, sample_fdp_root_rdf: str):
        """Test successful FDP metadata fetch."""
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body=sample_fdp_root_rdf,
            content_type='text/turtle',
        )

        client = FDPClient(timeout=30)
        fdp = client.fetch_fdp('https://example.org/fdp')

        assert fdp.uri == 'https://example.org/fdp'
        assert fdp.title == 'Example FAIR Data Point'
        assert 'sample FAIR Data Point' in fdp.description
        assert fdp.publisher == 'Example University'
        assert fdp.status == 'active'
        assert fdp.is_index is False
        assert 'https://example.org/fdp/catalog/research-data' in fdp.catalogs
        assert fdp.last_fetched is not None

    @responses.activate
    def test_fetch_fdp_index(self, sample_fdp_index_rdf: str):
        """Test fetching an index FDP with linked FDPs."""
        responses.add(
            responses.GET,
            'https://index.example.org/fdp',
            body=sample_fdp_index_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        fdp = client.fetch_fdp('https://index.example.org/fdp')

        assert fdp.is_index is True
        assert len(fdp.linked_fdps) == 2
        assert 'https://university-a.example.org/fdp' in fdp.linked_fdps
        assert 'https://university-b.example.org/fdp' in fdp.linked_fdps

    @responses.activate
    def test_fetch_fdp_connection_error(self):
        """Test handling of connection errors."""
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body=RequestsConnectionError("Connection refused"),
        )

        client = FDPClient()
        with pytest.raises(FDPConnectionError) as exc_info:
            client.fetch_fdp('https://example.org/fdp')

        assert 'Could not connect' in str(exc_info.value)

    @responses.activate
    def test_fetch_fdp_http_error(self):
        """Test handling of HTTP errors."""
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            status=404,
        )

        client = FDPClient()
        with pytest.raises(FDPConnectionError) as exc_info:
            client.fetch_fdp('https://example.org/fdp')

        assert '404' in str(exc_info.value)

    @responses.activate
    def test_fetch_fdp_parse_error(self):
        """Test handling of RDF parse errors."""
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body='not valid RDF content',
            content_type='text/turtle',
        )

        client = FDPClient()
        with pytest.raises(FDPParseError) as exc_info:
            client.fetch_fdp('https://example.org/fdp')

        assert 'Could not parse' in str(exc_info.value)

    @responses.activate
    def test_fetch_fdp_timeout(self):
        """Test handling of timeout errors."""
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body=Timeout("Request timed out"),
        )

        client = FDPClient(timeout=5)
        with pytest.raises(FDPTimeoutError) as exc_info:
            client.fetch_fdp('https://example.org/fdp')

        assert 'timed out' in str(exc_info.value)


class TestFDPClientFetchCatalog:
    """Tests for FDPClient.fetch_catalog()."""

    @responses.activate
    def test_fetch_catalog_success(self, sample_catalog_rdf: str):
        """Test successful catalog fetch."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/catalog/research-data',
            body=sample_catalog_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        catalog = client.fetch_catalog(
            'https://example.org/fdp/catalog/research-data',
            'https://example.org/fdp'
        )

        assert catalog.uri == 'https://example.org/fdp/catalog/research-data'
        assert catalog.title == 'Research Data Catalog'
        assert catalog.fdp_uri == 'https://example.org/fdp'
        assert len(catalog.datasets) == 3
        assert 'https://example.org/fdp/dataset/biodiversity-2023' in catalog.datasets

    @responses.activate
    def test_fetch_catalog_connection_error(self):
        """Test handling of connection errors for catalog fetch."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/catalog/test',
            body=RequestsConnectionError("Connection refused"),
        )

        client = FDPClient()
        with pytest.raises(FDPConnectionError):
            client.fetch_catalog(
                'https://example.org/fdp/catalog/test',
                'https://example.org/fdp'
            )


class TestFDPClientFetchDataset:
    """Tests for FDPClient.fetch_dataset()."""

    @responses.activate
    def test_fetch_dataset_success(self, sample_dataset_rdf: str):
        """Test successful dataset fetch with all fields."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/dataset/biodiversity-2023',
            body=sample_dataset_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        dataset = client.fetch_dataset(
            'https://example.org/fdp/dataset/biodiversity-2023',
            'https://example.org/fdp/catalog/research-data',
            'https://example.org/fdp',
            'Example FAIR Data Point'
        )

        assert dataset.uri == 'https://example.org/fdp/dataset/biodiversity-2023'
        assert dataset.title == 'Biodiversity Survey Data 2023'
        assert 'biodiversity survey' in dataset.description.lower()
        assert dataset.publisher == 'Example University'
        assert dataset.creator == 'Dr. Jane Smith'
        assert dataset.fdp_uri == 'https://example.org/fdp'
        assert dataset.fdp_title == 'Example FAIR Data Point'
        assert dataset.catalog_uri == 'https://example.org/fdp/catalog/research-data'

    @responses.activate
    def test_fetch_dataset_with_themes(self, sample_dataset_rdf: str):
        """Test dataset fetch with themes."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/dataset/biodiversity-2023',
            body=sample_dataset_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        dataset = client.fetch_dataset(
            'https://example.org/fdp/dataset/biodiversity-2023',
            'https://example.org/fdp/catalog/research-data',
            'https://example.org/fdp',
            'Example FAIR Data Point'
        )

        assert len(dataset.themes) >= 1
        assert any('Biodiversity' in label for label in dataset.theme_labels)

    @responses.activate
    def test_fetch_dataset_with_keywords(self, sample_dataset_rdf: str):
        """Test dataset fetch with keywords."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/dataset/biodiversity-2023',
            body=sample_dataset_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        dataset = client.fetch_dataset(
            'https://example.org/fdp/dataset/biodiversity-2023',
            'https://example.org/fdp/catalog/research-data',
            'https://example.org/fdp',
            'Example FAIR Data Point'
        )

        assert 'ecology' in dataset.keywords
        assert 'species' in dataset.keywords

    @responses.activate
    def test_fetch_dataset_with_contact(self, sample_dataset_rdf: str):
        """Test dataset fetch with contact point."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/dataset/biodiversity-2023',
            body=sample_dataset_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        dataset = client.fetch_dataset(
            'https://example.org/fdp/dataset/biodiversity-2023',
            'https://example.org/fdp/catalog/research-data',
            'https://example.org/fdp',
            'Example FAIR Data Point'
        )

        assert dataset.contact_point is not None
        assert dataset.contact_point.name == 'Research Data Team'
        assert dataset.contact_point.email == 'data-requests@example.org'

    @responses.activate
    def test_fetch_dataset_with_dates(self, sample_dataset_rdf: str):
        """Test dataset fetch with issued and modified dates."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/dataset/biodiversity-2023',
            body=sample_dataset_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        dataset = client.fetch_dataset(
            'https://example.org/fdp/dataset/biodiversity-2023',
            'https://example.org/fdp/catalog/research-data',
            'https://example.org/fdp',
            'Example FAIR Data Point'
        )

        assert dataset.issued is not None
        assert dataset.issued.year == 2023
        assert dataset.modified is not None

    @responses.activate
    def test_fetch_dataset_connection_error(self):
        """Test handling of connection errors for dataset fetch."""
        responses.add(
            responses.GET,
            'https://example.org/fdp/dataset/test',
            body=RequestsConnectionError("Connection refused"),
        )

        client = FDPClient()
        with pytest.raises(FDPConnectionError):
            client.fetch_dataset(
                'https://example.org/fdp/dataset/test',
                'https://example.org/fdp/catalog/research-data',
                'https://example.org/fdp',
                'Example FDP'
            )


class TestFDPClientHelpers:
    """Tests for FDPClient helper methods."""

    def test_exception_hierarchy(self):
        """Test that all exceptions inherit from FDPError."""
        assert issubclass(FDPConnectionError, FDPError)
        assert issubclass(FDPParseError, FDPError)
        assert issubclass(FDPTimeoutError, FDPError)

    def test_timeout_configuration(self):
        """Test that timeout can be configured."""
        client = FDPClient(timeout=60)
        assert client.timeout == 60

        client_default = FDPClient()
        assert client_default.timeout == 30


class TestFDPClientIndexDiscovery:
    """Tests for FDP index discovery functionality."""

    @responses.activate
    def test_discover_fdps_from_index(self, sample_fdp_index_rdf: str):
        """Test discovering FDP URIs from an index."""
        responses.add(
            responses.GET,
            'https://index.example.org/fdp',
            body=sample_fdp_index_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        linked_fdps = client.discover_fdps_from_index('https://index.example.org/fdp')

        assert len(linked_fdps) == 2
        assert 'https://university-a.example.org/fdp' in linked_fdps
        assert 'https://university-b.example.org/fdp' in linked_fdps

    @responses.activate
    def test_discover_fdps_from_non_index(self, sample_fdp_root_rdf: str):
        """Test discovering FDPs from a non-index FDP returns empty list."""
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body=sample_fdp_root_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        linked_fdps = client.discover_fdps_from_index('https://example.org/fdp')

        assert linked_fdps == []

    @responses.activate
    def test_fetch_all_from_index_success(
        self, sample_fdp_index_rdf: str, sample_fdp_root_rdf: str
    ):
        """Test fetching index and all linked FDPs."""
        # Mock the index FDP
        responses.add(
            responses.GET,
            'https://index.example.org/fdp',
            body=sample_fdp_index_rdf,
            content_type='text/turtle',
        )
        # Mock linked FDP A
        responses.add(
            responses.GET,
            'https://university-a.example.org/fdp',
            body=sample_fdp_root_rdf,
            content_type='text/turtle',
        )
        # Mock linked FDP B
        responses.add(
            responses.GET,
            'https://university-b.example.org/fdp',
            body=sample_fdp_root_rdf,
            content_type='text/turtle',
        )

        client = FDPClient()
        fdps = client.fetch_all_from_index('https://index.example.org/fdp')

        # Should have index + 2 linked FDPs
        assert len(fdps) == 3
        assert fdps[0].uri == 'https://index.example.org/fdp'
        assert fdps[0].is_index is True

    @responses.activate
    def test_fetch_all_from_index_partial_failure(
        self, sample_fdp_index_rdf: str, sample_fdp_root_rdf: str
    ):
        """Test that partial failures don't stop processing."""
        # Mock the index FDP
        responses.add(
            responses.GET,
            'https://index.example.org/fdp',
            body=sample_fdp_index_rdf,
            content_type='text/turtle',
        )
        # Mock linked FDP A - success
        responses.add(
            responses.GET,
            'https://university-a.example.org/fdp',
            body=sample_fdp_root_rdf,
            content_type='text/turtle',
        )
        # Mock linked FDP B - failure
        responses.add(
            responses.GET,
            'https://university-b.example.org/fdp',
            body=RequestsConnectionError("Connection refused"),
        )

        client = FDPClient()
        fdps = client.fetch_all_from_index('https://index.example.org/fdp')

        # Should still have 3 results (index + success + error placeholder)
        assert len(fdps) == 3

        # Check the error FDP
        error_fdp = next(f for f in fdps if f.uri == 'https://university-b.example.org/fdp')
        assert error_fdp.status == 'error'
        assert error_fdp.error_message is not None

    @responses.activate
    def test_fetch_all_from_index_connection_error(self):
        """Test that index connection error propagates."""
        responses.add(
            responses.GET,
            'https://index.example.org/fdp',
            body=RequestsConnectionError("Connection refused"),
        )

        client = FDPClient()
        with pytest.raises(FDPConnectionError):
            client.fetch_all_from_index('https://index.example.org/fdp')
