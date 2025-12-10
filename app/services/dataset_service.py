"""Dataset Service for aggregating and filtering datasets."""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any

from app.models import Dataset
from app.services.fdp_client import FDPClient, FDPError


logger = logging.getLogger(__name__)


@dataclass
class Theme:
    """Represents a theme for filtering datasets."""

    uri: str
    label: str
    count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'uri': self.uri,
            'label': self.label,
            'count': self.count,
        }


class DatasetService:
    """Service for aggregating and filtering datasets from FDPs."""

    def __init__(self, fdp_client: FDPClient):
        """
        Initialize the dataset service.

        Args:
            fdp_client: FDP client for fetching metadata.
        """
        self.fdp_client = fdp_client

    def get_all_datasets(self, fdp_uris: List[str]) -> List[Dataset]:
        """
        Fetch all datasets from the given FDPs.

        Optimized to extract dataset metadata from catalog RDF instead of
        making individual requests for each dataset.

        Args:
            fdp_uris: List of FDP URIs to fetch from.

        Returns:
            List of all datasets from all FDPs.
        """
        datasets = []

        for fdp_uri in fdp_uris:
            try:
                fdp = self.fdp_client.fetch_fdp(fdp_uri)
                logger.info(f"Fetching datasets from {len(fdp.catalogs)} catalogs in {fdp.title}")

                for catalog_uri in fdp.catalogs:
                    try:
                        # Use optimized method that extracts datasets from catalog RDF
                        catalog_datasets = self.fdp_client.fetch_catalog_with_datasets(
                            catalog_uri, fdp_uri, fdp.title
                        )
                        datasets.extend(catalog_datasets)
                    except FDPError as e:
                        logger.warning(f"Failed to fetch catalog {catalog_uri}: {e}")
            except FDPError as e:
                logger.warning(f"Failed to fetch FDP {fdp_uri}: {e}")

        logger.info(f"Total datasets fetched: {len(datasets)}")
        return datasets

    def filter_by_theme(
        self, datasets: List[Dataset], theme_uri: str
    ) -> List[Dataset]:
        """
        Filter datasets by theme URI.

        Args:
            datasets: Datasets to filter.
            theme_uri: Theme URI to filter by.

        Returns:
            Datasets that have the specified theme.
        """
        return [ds for ds in datasets if theme_uri in ds.themes]

    def filter_by_keyword(
        self, datasets: List[Dataset], keyword: str
    ) -> List[Dataset]:
        """
        Filter datasets containing keyword in title/description/keywords.

        Args:
            datasets: Datasets to filter.
            keyword: Keyword to search for (case-insensitive).

        Returns:
            Datasets containing the keyword.
        """
        keyword_lower = keyword.lower()
        result = []

        for ds in datasets:
            # Check title
            if ds.title and keyword_lower in ds.title.lower():
                result.append(ds)
                continue

            # Check description
            if ds.description and keyword_lower in ds.description.lower():
                result.append(ds)
                continue

            # Check keywords
            if any(keyword_lower in kw.lower() for kw in ds.keywords):
                result.append(ds)

        return result

    def search(self, datasets: List[Dataset], query: str) -> List[Dataset]:
        """
        Full-text search across dataset metadata.

        Searches across title, description, and keywords.
        Results are ordered by relevance:
        - Title match (highest priority)
        - Description match
        - Keyword match (lowest priority)

        Args:
            datasets: Datasets to search.
            query: Search query string (case-insensitive).

        Returns:
            Matching datasets, ordered by relevance.
        """
        if not query:
            return datasets

        query_lower = query.lower()
        query_terms = query_lower.split()

        scored_results = []

        for ds in datasets:
            score = 0
            title_lower = (ds.title or '').lower()
            desc_lower = (ds.description or '').lower()
            keywords_lower = [kw.lower() for kw in ds.keywords]

            for term in query_terms:
                # Title match (highest weight)
                if term in title_lower:
                    score += 100
                    # Bonus for exact title match
                    if title_lower == term:
                        score += 50

                # Description match
                if term in desc_lower:
                    score += 10

                # Keyword match
                if any(term in kw for kw in keywords_lower):
                    score += 5
                    # Bonus for exact keyword match
                    if term in keywords_lower:
                        score += 10

                # Theme label match
                theme_labels_lower = [tl.lower() for tl in ds.theme_labels]
                if any(term in tl for tl in theme_labels_lower):
                    score += 5

            if score > 0:
                scored_results.append((score, ds))

        # Sort by score (descending), then by title
        scored_results.sort(key=lambda x: (-x[0], x[1].title or ''))

        return [ds for _, ds in scored_results]

    def get_available_themes(self, datasets: List[Dataset]) -> List[Theme]:
        """
        Extract unique themes from datasets for filter UI.

        Args:
            datasets: Datasets to extract themes from.

        Returns:
            List of Theme objects with uri, label, and count.
        """
        theme_counts: Dict[str, Dict[str, Any]] = {}

        for ds in datasets:
            for i, theme_uri in enumerate(ds.themes):
                if theme_uri not in theme_counts:
                    # Try to get a label
                    label = ''
                    if i < len(ds.theme_labels):
                        label = ds.theme_labels[i]
                    if not label:
                        # Use the last part of the URI as a fallback label
                        label = theme_uri.split('/')[-1]

                    theme_counts[theme_uri] = {
                        'uri': theme_uri,
                        'label': label,
                        'count': 0,
                    }

                theme_counts[theme_uri]['count'] += 1

        # Convert to Theme objects and sort by count (descending)
        themes = [
            Theme(
                uri=data['uri'],
                label=data['label'],
                count=data['count'],
            )
            for data in theme_counts.values()
        ]

        themes.sort(key=lambda t: (-t.count, t.label))

        return themes
