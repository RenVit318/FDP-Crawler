"""FDP Client for fetching and parsing FAIR Data Point metadata."""

import logging
from datetime import datetime
from typing import Optional, List

import requests
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

from app.models import FairDataPoint, Catalog, Dataset, ContactPoint


logger = logging.getLogger(__name__)


# RDF Namespaces
DCAT = Namespace('http://www.w3.org/ns/dcat#')
DCT = Namespace('http://purl.org/dc/terms/')
FOAF = Namespace('http://xmlns.com/foaf/0.1/')
VCARD = Namespace('http://www.w3.org/2006/vcard/ns#')
FDP = Namespace('https://w3id.org/fdp/fdp-o#')
LDP = Namespace('http://www.w3.org/ns/ldp#')


class FDPError(Exception):
    """Base exception for FDP-related errors."""
    pass


class FDPConnectionError(FDPError):
    """Raised when an FDP cannot be reached."""
    pass


class FDPParseError(FDPError):
    """Raised when FDP RDF cannot be parsed."""
    pass


class FDPTimeoutError(FDPError):
    """Raised when FDP request times out."""
    pass


class FDPClient:
    """Client for fetching and parsing FAIR Data Point metadata."""

    def __init__(self, timeout: int = 30):
        """
        Initialize the FDP client.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self._headers = {
            'Accept': 'text/turtle, application/ld+json;q=0.9, application/rdf+xml;q=0.8'
        }

    def _fetch_rdf(self, uri: str) -> Graph:
        """
        Fetch RDF content from a URI and parse it into a Graph.

        Args:
            uri: The URI to fetch RDF from.

        Returns:
            An rdflib Graph containing the parsed RDF.

        Raises:
            FDPConnectionError: If the URI cannot be reached.
            FDPTimeoutError: If the request times out.
            FDPParseError: If the RDF cannot be parsed.
        """
        try:
            response = requests.get(uri, headers=self._headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout fetching {uri}: {e}")
            raise FDPTimeoutError(f"Request to {uri} timed out") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error fetching {uri}: {e}")
            raise FDPConnectionError(f"Could not connect to {uri}") from e
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching {uri}: {e}")
            raise FDPConnectionError(f"HTTP error for {uri}: {e.response.status_code}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching {uri}: {e}")
            raise FDPConnectionError(f"Request failed for {uri}") from e

        # Determine format from content-type
        content_type = response.headers.get('Content-Type', '')
        if 'turtle' in content_type:
            rdf_format = 'turtle'
        elif 'json' in content_type:
            rdf_format = 'json-ld'
        elif 'xml' in content_type:
            rdf_format = 'xml'
        else:
            # Default to turtle
            rdf_format = 'turtle'

        try:
            graph = Graph()
            graph.parse(data=response.text, format=rdf_format)
            return graph
        except Exception as e:
            logger.error(f"Parse error for {uri}: {e}")
            raise FDPParseError(f"Could not parse RDF from {uri}") from e

    def _get_literal_value(
        self, graph: Graph, subject: URIRef, predicate: URIRef
    ) -> Optional[str]:
        """Extract a literal value from the graph."""
        for obj in graph.objects(subject, predicate):
            if isinstance(obj, Literal):
                return str(obj)
            elif isinstance(obj, URIRef):
                # Try to get label for URI
                for label in graph.objects(obj, RDFS.label):
                    return str(label)
                # Or get foaf:name
                for name in graph.objects(obj, FOAF.name):
                    return str(name)
        return None

    def _get_uri_list(
        self, graph: Graph, subject: URIRef, predicate: URIRef
    ) -> List[str]:
        """Extract a list of URI values from the graph."""
        uris = []
        for obj in graph.objects(subject, predicate):
            if isinstance(obj, URIRef):
                uris.append(str(obj))
        return uris

    def _extract_contact_point(
        self, graph: Graph, dataset_uri: URIRef
    ) -> Optional[ContactPoint]:
        """
        Extract contact point information from a dataset.

        Args:
            graph: The RDF graph containing the dataset.
            dataset_uri: The URI of the dataset.

        Returns:
            A ContactPoint instance if found, None otherwise.
        """
        for contact_node in graph.objects(dataset_uri, DCAT.contactPoint):
            name = None
            email = None
            url = None

            # Get name (vcard:fn)
            for fn in graph.objects(contact_node, VCARD.fn):
                name = str(fn)
                break

            # Get email (vcard:hasEmail)
            for email_node in graph.objects(contact_node, VCARD.hasEmail):
                email_str = str(email_node)
                # Handle mailto: URIs
                if email_str.startswith('mailto:'):
                    email = email_str[7:]
                else:
                    email = email_str
                break

            # Get URL (vcard:hasURL)
            for url_node in graph.objects(contact_node, VCARD.hasURL):
                url = str(url_node)
                break

            if name or email or url:
                return ContactPoint(name=name, email=email, url=url)

        return None

    def _parse_date(self, value: Optional[str]) -> Optional[datetime]:
        """Parse a date string to datetime."""
        if not value:
            return None
        try:
            # Try ISO format first
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            pass
        try:
            # Try date only format
            return datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            pass
        return None

    def fetch_fdp(self, uri: str) -> FairDataPoint:
        """
        Fetch and parse FDP metadata.

        Args:
            uri: The FDP endpoint URL.

        Returns:
            FairDataPoint with metadata and catalog URIs.

        Raises:
            FDPConnectionError: If FDP is unreachable.
            FDPParseError: If RDF cannot be parsed.
        """
        graph = self._fetch_rdf(uri)
        fdp_uri = URIRef(uri)

        # Get title
        title = self._get_literal_value(graph, fdp_uri, DCT.title)
        if not title:
            title = self._get_literal_value(graph, fdp_uri, RDFS.label)
        if not title:
            title = uri

        # Get description
        description = self._get_literal_value(graph, fdp_uri, DCT.description)

        # Get publisher
        publisher = self._get_literal_value(graph, fdp_uri, DCT.publisher)

        # Get catalogs (via fdp:metadataCatalog or ldp:contains)
        catalogs = self._get_uri_list(graph, fdp_uri, FDP.metadataCatalog)
        if not catalogs:
            catalogs = self._get_uri_list(graph, fdp_uri, LDP.contains)

        # Check if this is an index FDP (has fdp:metadataService links)
        linked_fdps = self._get_uri_list(graph, fdp_uri, FDP.metadataService)
        is_index = len(linked_fdps) > 0

        return FairDataPoint(
            uri=uri,
            title=title,
            description=description,
            publisher=publisher,
            is_index=is_index,
            catalogs=catalogs,
            linked_fdps=linked_fdps,
            last_fetched=datetime.now(),
            status='active',
        )

    def fetch_catalog(self, uri: str, fdp_uri: str) -> Catalog:
        """
        Fetch and parse a catalog from an FDP.

        Args:
            uri: The catalog URI.
            fdp_uri: The parent FDP URI.

        Returns:
            Catalog with dataset URIs.

        Raises:
            FDPConnectionError: If catalog is unreachable.
            FDPParseError: If RDF cannot be parsed.
        """
        graph = self._fetch_rdf(uri)
        catalog_uri = URIRef(uri)

        # Get title
        title = self._get_literal_value(graph, catalog_uri, DCT.title)
        if not title:
            title = self._get_literal_value(graph, catalog_uri, RDFS.label)
        if not title:
            title = uri

        # Get description
        description = self._get_literal_value(graph, catalog_uri, DCT.description)

        # Get publisher
        publisher = self._get_literal_value(graph, catalog_uri, DCT.publisher)

        # Get datasets
        datasets = self._get_uri_list(graph, catalog_uri, DCAT.dataset)

        # Get themes
        themes = self._get_uri_list(graph, catalog_uri, DCAT.themeTaxonomy)

        return Catalog(
            uri=uri,
            title=title,
            description=description,
            publisher=publisher,
            fdp_uri=fdp_uri,
            datasets=datasets,
            themes=themes,
        )

    def fetch_dataset(
        self, uri: str, catalog_uri: str, fdp_uri: str, fdp_title: str
    ) -> Dataset:
        """
        Fetch and parse dataset metadata.

        Args:
            uri: The dataset URI.
            catalog_uri: Parent catalog URI.
            fdp_uri: Parent FDP URI.
            fdp_title: Parent FDP title for display.

        Returns:
            Dataset with full metadata.

        Raises:
            FDPConnectionError: If dataset is unreachable.
            FDPParseError: If RDF cannot be parsed.
        """
        graph = self._fetch_rdf(uri)
        dataset_uri = URIRef(uri)

        # Get title
        title = self._get_literal_value(graph, dataset_uri, DCT.title)
        if not title:
            title = self._get_literal_value(graph, dataset_uri, RDFS.label)
        if not title:
            title = uri

        # Get description
        description = self._get_literal_value(graph, dataset_uri, DCT.description)

        # Get publisher
        publisher = self._get_literal_value(graph, dataset_uri, DCT.publisher)

        # Get creator
        creator = self._get_literal_value(graph, dataset_uri, DCT.creator)

        # Get dates
        issued_str = self._get_literal_value(graph, dataset_uri, DCT.issued)
        issued = self._parse_date(issued_str)

        modified_str = self._get_literal_value(graph, dataset_uri, DCT.modified)
        modified = self._parse_date(modified_str)

        # Get themes
        themes = self._get_uri_list(graph, dataset_uri, DCAT.theme)

        # Get theme labels
        theme_labels = []
        for theme_uri in themes:
            label = self._get_literal_value(graph, URIRef(theme_uri), RDFS.label)
            if label:
                theme_labels.append(label)

        # Get keywords
        keywords = []
        for keyword in graph.objects(dataset_uri, DCAT.keyword):
            keywords.append(str(keyword))

        # Get contact point
        contact_point = self._extract_contact_point(graph, dataset_uri)

        # Get landing page
        landing_page = None
        for lp in graph.objects(dataset_uri, DCAT.landingPage):
            landing_page = str(lp)
            break

        # Get distributions
        distributions = self._get_uri_list(graph, dataset_uri, DCAT.distribution)

        return Dataset(
            uri=uri,
            title=title,
            description=description,
            publisher=publisher,
            creator=creator,
            issued=issued,
            modified=modified,
            themes=themes,
            theme_labels=theme_labels,
            keywords=keywords,
            contact_point=contact_point,
            landing_page=landing_page,
            catalog_uri=catalog_uri,
            fdp_uri=fdp_uri,
            fdp_title=fdp_title,
            distributions=distributions,
        )

    def discover_fdps_from_index(self, index_uri: str) -> List[str]:
        """
        Extract linked FDP URIs from an index FDP.

        Args:
            index_uri: URI of the index FDP.

        Returns:
            List of discovered FDP URIs.

        Raises:
            FDPConnectionError: If index FDP is unreachable.
            FDPParseError: If RDF cannot be parsed.
        """
        graph = self._fetch_rdf(index_uri)
        index_ref = URIRef(index_uri)

        # Get linked FDPs via fdp:metadataService
        linked_fdps = self._get_uri_list(graph, index_ref, FDP.metadataService)

        return linked_fdps

    def fetch_all_from_index(self, index_uri: str) -> List[FairDataPoint]:
        """
        Fetch the index FDP and all linked FDPs.

        Fetches the index, discovers linked FDPs, and fetches each one.
        Errors for individual FDPs are logged but don't stop processing.

        Args:
            index_uri: URI of the index FDP.

        Returns:
            List of FairDataPoint instances (index + all successfully fetched linked FDPs).

        Raises:
            FDPConnectionError: If index FDP is unreachable.
            FDPParseError: If index FDP cannot be parsed.
        """
        # First fetch the index itself
        index_fdp = self.fetch_fdp(index_uri)
        result = [index_fdp]

        # Then fetch all linked FDPs
        for linked_uri in index_fdp.linked_fdps:
            try:
                linked_fdp = self.fetch_fdp(linked_uri)
                result.append(linked_fdp)
                logger.info(f"Successfully fetched linked FDP: {linked_uri}")
            except FDPError as e:
                # Log error but continue with other FDPs
                logger.warning(f"Failed to fetch linked FDP {linked_uri}: {e}")
                # Add a placeholder FDP with error status
                error_fdp = FairDataPoint(
                    uri=linked_uri,
                    title=linked_uri,
                    is_index=False,
                    status='error',
                    error_message=str(e),
                )
                result.append(error_fdp)

        return result
