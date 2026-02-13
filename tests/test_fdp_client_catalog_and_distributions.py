"""Tests for FDPClient catalog fetching, distribution parsing, and SPARQL endpoint detection."""

import pytest
import responses
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

from app.services.fdp_client import FDPClient, FDPConnectionError, FDPParseError


DCAT = Namespace('http://www.w3.org/ns/dcat#')
DCT = Namespace('http://purl.org/dc/terms/')
VCARD = Namespace('http://www.w3.org/2006/vcard/ns#')
VOID = Namespace('http://rdfs.org/ns/void#')
LDP = Namespace('http://www.w3.org/ns/ldp#')


# ---------------------------------------------------------------------------
# RDF fixtures (inline turtle strings)
# ---------------------------------------------------------------------------

CATALOG_WITH_DATASETS_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix vcard: <http://www.w3.org/2006/vcard/ns#> .

<https://example.org/catalog/1>
    a dcat:Catalog ;
    dct:title "Test Catalog" ;
    dcat:dataset <https://example.org/dataset/alpha> ;
    dcat:dataset <https://example.org/dataset/beta> .

<https://example.org/dataset/alpha>
    a dcat:Dataset ;
    dct:title "Alpha Dataset" ;
    dct:description "First dataset" ;
    dct:publisher "Publisher A" ;
    dcat:theme <http://example.org/theme/bio> ;
    dcat:keyword "genetics" ;
    dcat:keyword "dna" ;
    dcat:contactPoint [
        a vcard:Kind ;
        vcard:fn "Contact Alpha" ;
        vcard:hasEmail <mailto:alpha@example.org>
    ] .

<https://example.org/dataset/beta>
    a dcat:Dataset ;
    dct:title "Beta Dataset" ;
    dct:description "Second dataset" .
"""

CATALOG_LDP_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix ldp:  <http://www.w3.org/ns/ldp#> .

<https://example.org/catalog/ldp>
    a dcat:Catalog ;
    dct:title "LDP Catalog" .

<https://example.org/catalog/ldp/container>
    a ldp:DirectContainer ;
    ldp:membershipResource <https://example.org/catalog/ldp> ;
    ldp:contains <https://example.org/dataset/gamma> .

<https://example.org/dataset/gamma>
    a dcat:Dataset ;
    dct:title "Gamma Dataset" .
"""

EMPTY_CATALOG_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .

<https://example.org/catalog/empty>
    a dcat:Catalog ;
    dct:title "Empty Catalog" .
"""

DISTRIBUTION_SPARQL_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix void: <http://rdfs.org/ns/void#> .
@prefix vcard: <http://www.w3.org/2006/vcard/ns#> .

<https://example.org/dist/sparql>
    a dcat:Distribution, dcat:DataService ;
    dct:title "SPARQL Endpoint" ;
    dct:description "A SPARQL endpoint distribution" ;
    dcat:accessURL <https://example.org/sparql> ;
    dcat:endpointURL <https://example.org/sparql> ;
    dcat:mediaType "application/sparql-results+json" ;
    dcat:contactPoint [
        a vcard:Kind ;
        vcard:fn "SPARQL Admin" ;
        vcard:hasEmail <mailto:sparql@example.org>
    ] .
"""

DISTRIBUTION_FILE_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .

<https://example.org/dist/csv>
    a dcat:Distribution ;
    dct:title "CSV Download" ;
    dct:description "CSV export" ;
    dcat:accessURL <https://example.org/data.csv> ;
    dcat:downloadURL <https://example.org/data.csv> ;
    dcat:mediaType "text/csv" ;
    dct:format "CSV" ;
    dcat:byteSize "1048576" .
"""

DISTRIBUTION_VOID_SPARQL_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix void: <http://rdfs.org/ns/void#> .

<https://example.org/dist/void-sparql>
    a dcat:Distribution ;
    dct:title "VoID SPARQL" ;
    void:sparqlEndpoint <https://example.org/repositories/main> .
"""

DISTRIBUTION_ACCESS_SERVICE_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .

<https://example.org/dist/via-service>
    a dcat:Distribution ;
    dct:title "Service Distribution" ;
    dcat:accessService <https://example.org/service/1> .

<https://example.org/service/1>
    a dcat:DataService ;
    dcat:endpointURL <https://example.org/service-sparql> .
"""

DISTRIBUTION_URL_HEURISTIC_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .

<https://example.org/dist/heuristic>
    a dcat:Distribution ;
    dct:title "Heuristic SPARQL" ;
    dcat:accessURL <https://example.org/repositories/myrepo> .
"""

DATASET_WITH_DISTRIBUTIONS_TTL = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<https://example.org/dataset/with-dists>
    a dcat:Dataset ;
    dct:title "Dataset With Distributions" ;
    dct:description "Has multiple distributions" ;
    dct:issued "2024-01-15"^^xsd:date ;
    dct:modified "2024-06-01T12:00:00Z"^^xsd:dateTime ;
    dcat:distribution <https://example.org/dist/inline-csv> ;
    dcat:distribution <https://example.org/dist/inline-sparql> .

<https://example.org/dist/inline-csv>
    a dcat:Distribution ;
    dct:title "Inline CSV" ;
    dcat:accessURL <https://example.org/data.csv> ;
    dcat:mediaType "text/csv" .

<https://example.org/dist/inline-sparql>
    a dcat:Distribution, dcat:DataService ;
    dct:title "Inline SPARQL" ;
    dcat:endpointURL <https://example.org/sparql> .
"""


# ===========================================================================
# Tests for fetch_catalog_with_datasets
# ===========================================================================


class TestFetchCatalogWithDatasets:
    """Tests for FDPClient.fetch_catalog_with_datasets()."""

    @responses.activate
    def test_fetches_datasets_via_dcat_dataset(self):
        """Test extracting datasets linked via dcat:dataset."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/1',
            body=CATALOG_WITH_DATASETS_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        datasets = client.fetch_catalog_with_datasets(
            'https://example.org/catalog/1',
            'https://example.org/fdp',
            'Test FDP',
        )

        assert len(datasets) == 2
        titles = {ds.title for ds in datasets}
        assert 'Alpha Dataset' in titles
        assert 'Beta Dataset' in titles

    @responses.activate
    def test_extracts_dataset_metadata(self):
        """Test that dataset metadata is correctly extracted from catalog RDF."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/1',
            body=CATALOG_WITH_DATASETS_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        datasets = client.fetch_catalog_with_datasets(
            'https://example.org/catalog/1',
            'https://example.org/fdp',
            'Test FDP',
        )

        alpha = next(ds for ds in datasets if ds.title == 'Alpha Dataset')
        assert alpha.description == 'First dataset'
        assert alpha.publisher == 'Publisher A'
        assert alpha.catalog_uri == 'https://example.org/catalog/1'
        assert alpha.fdp_uri == 'https://example.org/fdp'
        assert alpha.fdp_title == 'Test FDP'
        assert 'http://example.org/theme/bio' in alpha.themes
        assert 'genetics' in alpha.keywords
        assert 'dna' in alpha.keywords

    @responses.activate
    def test_extracts_contact_point(self):
        """Test contact point extraction from catalog-embedded datasets."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/1',
            body=CATALOG_WITH_DATASETS_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        datasets = client.fetch_catalog_with_datasets(
            'https://example.org/catalog/1',
            'https://example.org/fdp',
            'Test FDP',
        )

        alpha = next(ds for ds in datasets if ds.title == 'Alpha Dataset')
        assert alpha.contact_point is not None
        assert alpha.contact_point.name == 'Contact Alpha'
        assert alpha.contact_point.email == 'alpha@example.org'

    @responses.activate
    def test_dataset_without_optional_fields(self):
        """Test dataset with only title (no description, publisher, etc.)."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/1',
            body=CATALOG_WITH_DATASETS_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        datasets = client.fetch_catalog_with_datasets(
            'https://example.org/catalog/1',
            'https://example.org/fdp',
            'Test FDP',
        )

        beta = next(ds for ds in datasets if ds.title == 'Beta Dataset')
        assert beta.description == 'Second dataset'
        assert beta.publisher is None
        assert beta.contact_point is None
        assert beta.keywords == []
        assert beta.themes == []

    @responses.activate
    def test_discovers_datasets_via_ldp_container(self):
        """Test dataset discovery through LDP DirectContainer."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/ldp',
            body=CATALOG_LDP_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        datasets = client.fetch_catalog_with_datasets(
            'https://example.org/catalog/ldp',
            'https://example.org/fdp',
            'Test FDP',
        )

        assert len(datasets) == 1
        assert datasets[0].title == 'Gamma Dataset'

    @responses.activate
    def test_empty_catalog_returns_no_datasets(self):
        """Test that an empty catalog returns an empty list."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/empty',
            body=EMPTY_CATALOG_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        datasets = client.fetch_catalog_with_datasets(
            'https://example.org/catalog/empty',
            'https://example.org/fdp',
            'Test FDP',
        )

        assert datasets == []

    @responses.activate
    def test_catalog_title_extracted(self):
        """Test that catalog_title is set on returned datasets."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/1',
            body=CATALOG_WITH_DATASETS_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        datasets = client.fetch_catalog_with_datasets(
            'https://example.org/catalog/1',
            'https://example.org/fdp',
            'Test FDP',
        )

        for ds in datasets:
            assert ds.catalog_title == 'Test Catalog'

    @responses.activate
    def test_connection_error_propagates(self):
        """Test that connection errors propagate correctly."""
        from requests.exceptions import ConnectionError as RequestsConnectionError

        responses.add(
            responses.GET,
            'https://example.org/catalog/fail',
            body=RequestsConnectionError("Connection refused"),
        )

        client = FDPClient()
        with pytest.raises(FDPConnectionError):
            client.fetch_catalog_with_datasets(
                'https://example.org/catalog/fail',
                'https://example.org/fdp',
                'Test FDP',
            )

    @responses.activate
    def test_parse_error_propagates(self):
        """Test that parse errors propagate correctly."""
        responses.add(
            responses.GET,
            'https://example.org/catalog/bad',
            body='this is not valid turtle',
            content_type='text/turtle',
        )

        client = FDPClient()
        with pytest.raises(FDPParseError):
            client.fetch_catalog_with_datasets(
                'https://example.org/catalog/bad',
                'https://example.org/fdp',
                'Test FDP',
            )


# ===========================================================================
# Tests for fetch_distribution
# ===========================================================================


class TestFetchDistribution:
    """Tests for FDPClient.fetch_distribution()."""

    @responses.activate
    def test_fetch_sparql_distribution(self):
        """Test fetching a SPARQL endpoint distribution."""
        responses.add(
            responses.GET,
            'https://example.org/dist/sparql',
            body=DISTRIBUTION_SPARQL_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        dist = client.fetch_distribution('https://example.org/dist/sparql')

        assert dist.uri == 'https://example.org/dist/sparql'
        assert dist.title == 'SPARQL Endpoint'
        assert dist.description == 'A SPARQL endpoint distribution'
        assert dist.access_url == 'https://example.org/sparql'
        assert dist.endpoint_url == 'https://example.org/sparql'
        assert dist.is_sparql_endpoint is True
        assert dist.media_type == 'application/sparql-results+json'

    @responses.activate
    def test_fetch_file_distribution(self):
        """Test fetching a file download distribution."""
        responses.add(
            responses.GET,
            'https://example.org/dist/csv',
            body=DISTRIBUTION_FILE_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        dist = client.fetch_distribution('https://example.org/dist/csv')

        assert dist.title == 'CSV Download'
        assert dist.access_url == 'https://example.org/data.csv'
        assert dist.download_url == 'https://example.org/data.csv'
        assert dist.media_type == 'text/csv'
        assert dist.format == 'CSV'
        assert dist.byte_size == 1048576
        assert dist.is_sparql_endpoint is False
        assert dist.endpoint_url is None

    @responses.activate
    def test_fetch_distribution_with_contact(self):
        """Test distribution-level contact point extraction."""
        responses.add(
            responses.GET,
            'https://example.org/dist/sparql',
            body=DISTRIBUTION_SPARQL_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        dist = client.fetch_distribution('https://example.org/dist/sparql')

        assert dist.contact_point is not None
        assert dist.contact_point.name == 'SPARQL Admin'
        assert dist.contact_point.email == 'sparql@example.org'

    def test_fetch_distribution_with_provided_graph(self):
        """Test distribution extraction from a pre-fetched graph."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_FILE_TTL, format='turtle')

        client = FDPClient()
        dist = client.fetch_distribution('https://example.org/dist/csv', graph=graph)

        assert dist.title == 'CSV Download'
        assert dist.download_url == 'https://example.org/data.csv'

    @responses.activate
    def test_fetch_distribution_connection_failure_returns_minimal(self):
        """Test that a failed fetch returns a minimal Distribution."""
        from requests.exceptions import ConnectionError as RequestsConnectionError

        responses.add(
            responses.GET,
            'https://example.org/dist/broken',
            body=RequestsConnectionError("Connection refused"),
        )

        client = FDPClient()
        dist = client.fetch_distribution('https://example.org/dist/broken')

        assert dist.uri == 'https://example.org/dist/broken'
        assert dist.title is None
        assert dist.access_url is None
        assert dist.is_sparql_endpoint is False

    def test_fetch_distribution_invalid_byte_size(self):
        """Test that non-integer byte_size is handled gracefully."""
        ttl = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct:  <http://purl.org/dc/terms/> .

<https://example.org/dist/bad-size>
    a dcat:Distribution ;
    dct:title "Bad Size" ;
    dcat:byteSize "not-a-number" .
"""
        graph = Graph()
        graph.parse(data=ttl, format='turtle')

        client = FDPClient()
        dist = client.fetch_distribution('https://example.org/dist/bad-size', graph=graph)

        assert dist.byte_size is None


# ===========================================================================
# Tests for SPARQL endpoint detection (_is_sparql_endpoint, _extract_endpoint_url)
# ===========================================================================


class TestSPARQLEndpointDetection:
    """Tests for _is_sparql_endpoint() and _extract_endpoint_url()."""

    def _make_client(self):
        return FDPClient()

    def test_detects_data_service_type(self):
        """Test detection via dcat:DataService rdf:type."""
        graph = Graph()
        node = URIRef('https://example.org/dist')
        graph.add((node, RDF.type, DCAT.DataService))

        client = self._make_client()
        assert client._is_sparql_endpoint(graph, node) is True

    def test_detects_void_sparql_endpoint(self):
        """Test detection via void:sparqlEndpoint property."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_VOID_SPARQL_TTL, format='turtle')
        node = URIRef('https://example.org/dist/void-sparql')

        client = self._make_client()
        assert client._is_sparql_endpoint(graph, node) is True

    def test_detects_dcat_endpoint_url(self):
        """Test detection via dcat:endpointURL property."""
        graph = Graph()
        node = URIRef('https://example.org/dist')
        graph.add((node, DCAT.endpointURL, URIRef('https://example.org/sparql')))

        client = self._make_client()
        assert client._is_sparql_endpoint(graph, node) is True

    def test_detects_url_heuristic_sparql(self):
        """Test detection via URL heuristic containing 'sparql'."""
        graph = Graph()
        node = URIRef('https://example.org/dist')
        graph.add((node, DCAT.accessURL, URIRef('https://example.org/sparql/query')))

        client = self._make_client()
        assert client._is_sparql_endpoint(graph, node) is True

    def test_detects_url_heuristic_repositories(self):
        """Test detection via URL heuristic containing 'repositories'."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_URL_HEURISTIC_TTL, format='turtle')
        node = URIRef('https://example.org/dist/heuristic')

        client = self._make_client()
        assert client._is_sparql_endpoint(graph, node) is True

    def test_not_sparql_for_plain_distribution(self):
        """Test that a plain file distribution is not detected as SPARQL."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_FILE_TTL, format='turtle')
        node = URIRef('https://example.org/dist/csv')

        client = self._make_client()
        assert client._is_sparql_endpoint(graph, node) is False

    def test_extract_endpoint_url_via_dcat_endpoint_url(self):
        """Test endpoint URL extraction via dcat:endpointURL."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_SPARQL_TTL, format='turtle')
        node = URIRef('https://example.org/dist/sparql')

        client = self._make_client()
        url = client._extract_endpoint_url(graph, node)
        assert url == 'https://example.org/sparql'

    def test_extract_endpoint_url_via_void(self):
        """Test endpoint URL extraction via void:sparqlEndpoint."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_VOID_SPARQL_TTL, format='turtle')
        node = URIRef('https://example.org/dist/void-sparql')

        client = self._make_client()
        url = client._extract_endpoint_url(graph, node)
        assert url == 'https://example.org/repositories/main'

    def test_extract_endpoint_url_via_access_service(self):
        """Test endpoint URL extraction via dcat:accessService indirection."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_ACCESS_SERVICE_TTL, format='turtle')
        node = URIRef('https://example.org/dist/via-service')

        client = self._make_client()
        url = client._extract_endpoint_url(graph, node)
        assert url == 'https://example.org/service-sparql'

    def test_extract_endpoint_url_via_heuristic_access_url(self):
        """Test endpoint URL extraction via accessURL heuristic fallback."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_URL_HEURISTIC_TTL, format='turtle')
        node = URIRef('https://example.org/dist/heuristic')

        client = self._make_client()
        url = client._extract_endpoint_url(graph, node)
        assert url == 'https://example.org/repositories/myrepo'

    def test_extract_endpoint_url_returns_none_for_plain(self):
        """Test that plain distributions return None for endpoint URL."""
        graph = Graph()
        graph.parse(data=DISTRIBUTION_FILE_TTL, format='turtle')
        node = URIRef('https://example.org/dist/csv')

        client = self._make_client()
        url = client._extract_endpoint_url(graph, node)
        assert url is None


# ===========================================================================
# Tests for fetch_dataset with distributions
# ===========================================================================


class TestFetchDatasetDistributions:
    """Tests for fetch_dataset() distribution handling."""

    @responses.activate
    def test_fetch_dataset_with_inline_distributions(self):
        """Test that inline distributions are parsed from the dataset graph."""
        responses.add(
            responses.GET,
            'https://example.org/dataset/with-dists',
            body=DATASET_WITH_DISTRIBUTIONS_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        dataset = client.fetch_dataset(
            'https://example.org/dataset/with-dists',
            'https://example.org/catalog/1',
            'https://example.org/fdp',
            'Test FDP',
        )

        assert len(dataset.distributions) == 2
        titles = {d.title for d in dataset.distributions}
        assert 'Inline CSV' in titles
        assert 'Inline SPARQL' in titles

        sparql_dist = next(d for d in dataset.distributions if d.title == 'Inline SPARQL')
        assert sparql_dist.is_sparql_endpoint is True
        assert sparql_dist.endpoint_url == 'https://example.org/sparql'

    @responses.activate
    def test_fetch_dataset_dates_parsed(self):
        """Test that issued and modified dates are parsed correctly."""
        responses.add(
            responses.GET,
            'https://example.org/dataset/with-dists',
            body=DATASET_WITH_DISTRIBUTIONS_TTL,
            content_type='text/turtle',
        )

        client = FDPClient()
        dataset = client.fetch_dataset(
            'https://example.org/dataset/with-dists',
            'https://example.org/catalog/1',
            'https://example.org/fdp',
            'Test FDP',
        )

        assert dataset.issued is not None
        assert dataset.issued.year == 2024
        assert dataset.issued.month == 1
        assert dataset.modified is not None


# ===========================================================================
# Tests for _parse_date
# ===========================================================================


class TestParseDate:
    """Tests for FDPClient._parse_date()."""

    def test_iso_format(self):
        client = FDPClient()
        result = client._parse_date('2024-01-15T12:00:00')
        assert result is not None
        assert result.year == 2024

    def test_iso_format_with_z(self):
        client = FDPClient()
        result = client._parse_date('2024-01-15T12:00:00Z')
        assert result is not None
        assert result.year == 2024

    def test_date_only_format(self):
        client = FDPClient()
        result = client._parse_date('2024-01-15')
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_none_input(self):
        client = FDPClient()
        assert client._parse_date(None) is None

    def test_empty_string(self):
        client = FDPClient()
        assert client._parse_date('') is None

    def test_unparseable_string(self):
        client = FDPClient()
        assert client._parse_date('not-a-date') is None


# ===========================================================================
# Tests for _fetch_rdf content-type handling
# ===========================================================================


class TestFetchRdfContentType:
    """Tests for _fetch_rdf content-type detection."""

    @responses.activate
    def test_json_ld_content_type(self):
        """Test that application/ld+json is handled."""
        jsonld = '''
        {
            "@context": {"dct": "http://purl.org/dc/terms/"},
            "@id": "https://example.org/fdp",
            "dct:title": "JSON-LD FDP"
        }
        '''
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body=jsonld,
            content_type='application/ld+json',
        )

        client = FDPClient()
        graph = client._fetch_rdf('https://example.org/fdp')
        assert len(graph) > 0

    @responses.activate
    def test_default_content_type_falls_back_to_turtle(self):
        """Test that unknown content types default to turtle parsing."""
        ttl = '<https://example.org/x> <http://purl.org/dc/terms/title> "Test" .'
        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body=ttl,
            content_type='text/plain',
        )

        client = FDPClient()
        graph = client._fetch_rdf('https://example.org/fdp')
        assert len(graph) == 1

    @responses.activate
    def test_generic_request_exception(self):
        """Test that generic RequestException is caught."""
        from requests.exceptions import RequestException

        responses.add(
            responses.GET,
            'https://example.org/fdp',
            body=RequestException("Something went wrong"),
        )

        client = FDPClient()
        with pytest.raises(FDPConnectionError) as exc_info:
            client._fetch_rdf('https://example.org/fdp')
        assert 'Request failed' in str(exc_info.value)
