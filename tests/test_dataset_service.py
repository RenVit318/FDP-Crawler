"""Tests for the Dataset Service."""

import pytest
from unittest.mock import Mock, MagicMock

from app.models import Dataset, ContactPoint
from app.services.dataset_service import DatasetService, Theme
from app.services.fdp_client import FDPClient, FDPConnectionError


@pytest.fixture
def mock_fdp_client():
    """Create a mock FDP client."""
    return Mock(spec=FDPClient)


@pytest.fixture
def sample_datasets() -> list:
    """Create sample datasets for testing."""
    return [
        Dataset(
            uri='https://example.org/dataset/1',
            title='Biodiversity Survey Data',
            description='Annual biodiversity survey results covering species observations.',
            publisher='Example University',
            themes=['http://www.wikidata.org/entity/Q47041'],
            theme_labels=['Biodiversity'],
            keywords=['ecology', 'species', 'survey'],
            catalog_uri='https://example.org/catalog/1',
            fdp_uri='https://example.org/fdp',
            fdp_title='Example FDP',
        ),
        Dataset(
            uri='https://example.org/dataset/2',
            title='Climate Observations',
            description='Long-term climate monitoring data from weather stations.',
            publisher='Weather Institute',
            themes=['http://www.wikidata.org/entity/Q7937'],
            theme_labels=['Climate'],
            keywords=['weather', 'temperature', 'precipitation'],
            catalog_uri='https://example.org/catalog/1',
            fdp_uri='https://example.org/fdp',
            fdp_title='Example FDP',
        ),
        Dataset(
            uri='https://example.org/dataset/3',
            title='Genomics Study Results',
            description='Genomic sequencing data from clinical studies.',
            publisher='Medical Research Center',
            themes=['http://www.wikidata.org/entity/Q7020'],
            theme_labels=['Genomics'],
            keywords=['genetics', 'dna', 'sequencing', 'clinical'],
            catalog_uri='https://example.org/catalog/1',
            fdp_uri='https://example.org/fdp',
            fdp_title='Example FDP',
        ),
        Dataset(
            uri='https://example.org/dataset/4',
            title='Species Distribution Maps',
            description='Geographic distribution data for endangered species.',
            publisher='Conservation Society',
            themes=['http://www.wikidata.org/entity/Q47041'],
            theme_labels=['Biodiversity'],
            keywords=['ecology', 'species', 'conservation', 'maps'],
            catalog_uri='https://example.org/catalog/2',
            fdp_uri='https://example.org/fdp2',
            fdp_title='Another FDP',
        ),
    ]


class TestDatasetServiceFilter:
    """Tests for DatasetService filtering methods."""

    def test_filter_by_theme(self, mock_fdp_client, sample_datasets):
        """Test filtering datasets by theme URI."""
        service = DatasetService(mock_fdp_client)

        # Filter for biodiversity theme
        result = service.filter_by_theme(
            sample_datasets,
            'http://www.wikidata.org/entity/Q47041'
        )

        assert len(result) == 2
        assert all('Biodiversity' in ds.theme_labels for ds in result)

    def test_filter_by_theme_no_match(self, mock_fdp_client, sample_datasets):
        """Test filtering with no matching theme."""
        service = DatasetService(mock_fdp_client)

        result = service.filter_by_theme(
            sample_datasets,
            'http://www.wikidata.org/entity/NONEXISTENT'
        )

        assert len(result) == 0

    def test_filter_by_keyword_in_title(self, mock_fdp_client, sample_datasets):
        """Test filtering by keyword found in title."""
        service = DatasetService(mock_fdp_client)

        result = service.filter_by_keyword(sample_datasets, 'biodiversity')

        assert len(result) == 1
        assert result[0].title == 'Biodiversity Survey Data'

    def test_filter_by_keyword_in_description(self, mock_fdp_client, sample_datasets):
        """Test filtering by keyword found in description."""
        service = DatasetService(mock_fdp_client)

        result = service.filter_by_keyword(sample_datasets, 'weather')

        assert len(result) == 1
        assert result[0].title == 'Climate Observations'

    def test_filter_by_keyword_in_keywords(self, mock_fdp_client, sample_datasets):
        """Test filtering by keyword found in keywords list."""
        service = DatasetService(mock_fdp_client)

        result = service.filter_by_keyword(sample_datasets, 'genetics')

        assert len(result) == 1
        assert result[0].title == 'Genomics Study Results'

    def test_filter_by_keyword_case_insensitive(self, mock_fdp_client, sample_datasets):
        """Test that keyword filtering is case-insensitive."""
        service = DatasetService(mock_fdp_client)

        result_upper = service.filter_by_keyword(sample_datasets, 'ECOLOGY')
        result_lower = service.filter_by_keyword(sample_datasets, 'ecology')
        result_mixed = service.filter_by_keyword(sample_datasets, 'Ecology')

        assert len(result_upper) == len(result_lower) == len(result_mixed) == 2


class TestDatasetServiceSearch:
    """Tests for DatasetService search method."""

    def test_search_title_match(self, mock_fdp_client, sample_datasets):
        """Test search with title match gets highest priority."""
        service = DatasetService(mock_fdp_client)

        result = service.search(sample_datasets, 'climate')

        assert len(result) >= 1
        assert result[0].title == 'Climate Observations'

    def test_search_multiple_terms(self, mock_fdp_client, sample_datasets):
        """Test search with multiple terms."""
        service = DatasetService(mock_fdp_client)

        result = service.search(sample_datasets, 'species ecology')

        assert len(result) >= 1
        # Datasets with both terms should rank higher
        assert any('species' in ds.title.lower() or 'species' in ds.description.lower()
                   for ds in result)

    def test_search_case_insensitive(self, mock_fdp_client, sample_datasets):
        """Test that search is case-insensitive."""
        service = DatasetService(mock_fdp_client)

        result_upper = service.search(sample_datasets, 'GENOMICS')
        result_lower = service.search(sample_datasets, 'genomics')

        assert len(result_upper) == len(result_lower)

    def test_search_no_match(self, mock_fdp_client, sample_datasets):
        """Test search with no matches."""
        service = DatasetService(mock_fdp_client)

        result = service.search(sample_datasets, 'nonexistent query xyz')

        assert len(result) == 0

    def test_search_empty_query(self, mock_fdp_client, sample_datasets):
        """Test search with empty query returns all datasets."""
        service = DatasetService(mock_fdp_client)

        result = service.search(sample_datasets, '')

        assert len(result) == len(sample_datasets)

    def test_search_relevance_ordering(self, mock_fdp_client, sample_datasets):
        """Test that search results are ordered by relevance."""
        service = DatasetService(mock_fdp_client)

        # 'species' appears in title of one dataset and keywords of two
        result = service.search(sample_datasets, 'species')

        # Dataset with 'species' in title should come first
        assert len(result) >= 1
        assert 'Species' in result[0].title


class TestDatasetServiceThemes:
    """Tests for DatasetService theme extraction."""

    def test_get_available_themes(self, mock_fdp_client, sample_datasets):
        """Test extracting available themes."""
        service = DatasetService(mock_fdp_client)

        themes = service.get_available_themes(sample_datasets)

        assert len(themes) == 3  # Biodiversity, Climate, Genomics
        # Check that Theme objects have correct structure
        assert all(isinstance(t, Theme) for t in themes)
        assert all(t.uri and t.label and t.count > 0 for t in themes)

    def test_theme_counts(self, mock_fdp_client, sample_datasets):
        """Test that theme counts are accurate."""
        service = DatasetService(mock_fdp_client)

        themes = service.get_available_themes(sample_datasets)

        # Find biodiversity theme (should have count of 2)
        biodiversity = next(t for t in themes if 'Biodiversity' in t.label)
        assert biodiversity.count == 2

    def test_themes_sorted_by_count(self, mock_fdp_client, sample_datasets):
        """Test that themes are sorted by count descending."""
        service = DatasetService(mock_fdp_client)

        themes = service.get_available_themes(sample_datasets)

        # Themes should be sorted by count (descending)
        for i in range(len(themes) - 1):
            assert themes[i].count >= themes[i + 1].count

    def test_theme_to_dict(self):
        """Test Theme.to_dict() method."""
        theme = Theme(
            uri='http://example.org/theme/1',
            label='Test Theme',
            count=5
        )

        d = theme.to_dict()

        assert d['uri'] == 'http://example.org/theme/1'
        assert d['label'] == 'Test Theme'
        assert d['count'] == 5


class TestDatasetServiceGetAll:
    """Tests for DatasetService.get_all_datasets()."""

    def test_get_all_datasets_success(self, mock_fdp_client):
        """Test successfully fetching all datasets."""
        # Set up mock responses
        mock_fdp = MagicMock()
        mock_fdp.title = 'Test FDP'
        mock_fdp.catalogs = ['https://example.org/catalog/1']

        mock_catalog = MagicMock()
        mock_catalog.datasets = ['https://example.org/dataset/1']

        mock_dataset = Dataset(
            uri='https://example.org/dataset/1',
            title='Test Dataset',
            catalog_uri='https://example.org/catalog/1',
            fdp_uri='https://example.org/fdp',
            fdp_title='Test FDP',
        )

        mock_fdp_client.fetch_fdp.return_value = mock_fdp
        mock_fdp_client.fetch_catalog.return_value = mock_catalog
        mock_fdp_client.fetch_dataset.return_value = mock_dataset

        service = DatasetService(mock_fdp_client)
        result = service.get_all_datasets(['https://example.org/fdp'])

        assert len(result) == 1
        assert result[0].title == 'Test Dataset'

    def test_get_all_datasets_handles_fdp_error(self, mock_fdp_client):
        """Test that FDP errors are handled gracefully."""
        mock_fdp_client.fetch_fdp.side_effect = FDPConnectionError("Connection failed")

        service = DatasetService(mock_fdp_client)
        result = service.get_all_datasets(['https://example.org/fdp'])

        # Should return empty list without crashing
        assert result == []

    def test_get_all_datasets_handles_catalog_error(self, mock_fdp_client):
        """Test that catalog errors are handled gracefully."""
        mock_fdp = MagicMock()
        mock_fdp.title = 'Test FDP'
        mock_fdp.catalogs = ['https://example.org/catalog/1']

        mock_fdp_client.fetch_fdp.return_value = mock_fdp
        mock_fdp_client.fetch_catalog.side_effect = FDPConnectionError("Connection failed")

        service = DatasetService(mock_fdp_client)
        result = service.get_all_datasets(['https://example.org/fdp'])

        # Should return empty list without crashing
        assert result == []

    def test_get_all_datasets_handles_dataset_error(self, mock_fdp_client):
        """Test that dataset errors are handled gracefully."""
        mock_fdp = MagicMock()
        mock_fdp.title = 'Test FDP'
        mock_fdp.catalogs = ['https://example.org/catalog/1']

        mock_catalog = MagicMock()
        mock_catalog.datasets = ['https://example.org/dataset/1', 'https://example.org/dataset/2']

        mock_dataset = Dataset(
            uri='https://example.org/dataset/2',
            title='Test Dataset 2',
            catalog_uri='https://example.org/catalog/1',
            fdp_uri='https://example.org/fdp',
            fdp_title='Test FDP',
        )

        mock_fdp_client.fetch_fdp.return_value = mock_fdp
        mock_fdp_client.fetch_catalog.return_value = mock_catalog
        # First dataset fails, second succeeds
        mock_fdp_client.fetch_dataset.side_effect = [
            FDPConnectionError("Connection failed"),
            mock_dataset,
        ]

        service = DatasetService(mock_fdp_client)
        result = service.get_all_datasets(['https://example.org/fdp'])

        # Should return the successful dataset
        assert len(result) == 1
        assert result[0].title == 'Test Dataset 2'

    def test_get_all_datasets_multiple_fdps(self, mock_fdp_client):
        """Test fetching from multiple FDPs."""
        mock_fdp1 = MagicMock()
        mock_fdp1.title = 'FDP 1'
        mock_fdp1.catalogs = ['https://example.org/catalog/1']

        mock_fdp2 = MagicMock()
        mock_fdp2.title = 'FDP 2'
        mock_fdp2.catalogs = ['https://other.org/catalog/1']

        mock_catalog1 = MagicMock()
        mock_catalog1.datasets = ['https://example.org/dataset/1']

        mock_catalog2 = MagicMock()
        mock_catalog2.datasets = ['https://other.org/dataset/1']

        mock_dataset1 = Dataset(
            uri='https://example.org/dataset/1',
            title='Dataset 1',
            catalog_uri='https://example.org/catalog/1',
            fdp_uri='https://example.org/fdp',
            fdp_title='FDP 1',
        )

        mock_dataset2 = Dataset(
            uri='https://other.org/dataset/1',
            title='Dataset 2',
            catalog_uri='https://other.org/catalog/1',
            fdp_uri='https://other.org/fdp',
            fdp_title='FDP 2',
        )

        mock_fdp_client.fetch_fdp.side_effect = [mock_fdp1, mock_fdp2]
        mock_fdp_client.fetch_catalog.side_effect = [mock_catalog1, mock_catalog2]
        mock_fdp_client.fetch_dataset.side_effect = [mock_dataset1, mock_dataset2]

        service = DatasetService(mock_fdp_client)
        result = service.get_all_datasets([
            'https://example.org/fdp',
            'https://other.org/fdp'
        ])

        assert len(result) == 2
