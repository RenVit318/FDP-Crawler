# Data Visiting PoC - Data Models & Interface Definitions

This document defines the data structures used throughout the application. All components must adhere to these definitions to ensure interoperability.

## Core Data Models

### 1. FairDataPoint

Represents a FAIR Data Point endpoint.

```python
@dataclass
class FairDataPoint:
    """Represents a FAIR Data Point endpoint."""
    
    uri: str                      # The FDP endpoint URL
    title: str                    # Human-readable name
    description: Optional[str]    # Description of the FDP
    publisher: Optional[str]      # Organization running the FDP
    is_index: bool               # True if this is an index FDP
    catalogs: List[str]          # URIs of catalogs in this FDP
    linked_fdps: List[str]       # URIs of linked FDPs (if index)
    last_fetched: Optional[datetime]  # When metadata was last retrieved
    status: str                  # 'active', 'error', 'pending'
    error_message: Optional[str] # Error details if status is 'error'
```

**JSON Representation:**
```json
{
  "uri": "https://example.org/fdp",
  "title": "Example FAIR Data Point",
  "description": "A repository of research datasets",
  "publisher": "Example University",
  "is_index": false,
  "catalogs": ["https://example.org/fdp/catalog/1"],
  "linked_fdps": [],
  "last_fetched": "2024-01-15T10:30:00Z",
  "status": "active",
  "error_message": null
}
```

---

### 2. Catalog

Represents a DCAT Catalog within an FDP.

```python
@dataclass
class Catalog:
    """Represents a DCAT Catalog."""
    
    uri: str                      # Catalog URI
    title: str                    # Catalog title
    description: Optional[str]    # Catalog description
    publisher: Optional[str]      # Publisher name
    fdp_uri: str                  # Parent FDP URI
    datasets: List[str]          # URIs of datasets in this catalog
    themes: List[str]            # Theme URIs used in this catalog
```

**JSON Representation:**
```json
{
  "uri": "https://example.org/fdp/catalog/1",
  "title": "Research Data Catalog",
  "description": "Catalog of research datasets",
  "publisher": "Example University",
  "fdp_uri": "https://example.org/fdp",
  "datasets": [
    "https://example.org/fdp/dataset/123",
    "https://example.org/fdp/dataset/456"
  ],
  "themes": [
    "http://www.wikidata.org/entity/Q420",
    "http://www.wikidata.org/entity/Q7150"
  ]
}
```

---

### 3. Dataset

Represents a DCAT Dataset with all relevant metadata for discovery.

```python
@dataclass
class Dataset:
    """Represents a DCAT Dataset."""
    
    uri: str                      # Dataset URI
    title: str                    # Dataset title
    description: Optional[str]    # Dataset description
    
    # Provenance
    publisher: Optional[str]      # Publisher name
    creator: Optional[str]        # Creator/author
    issued: Optional[datetime]    # Publication date
    modified: Optional[datetime]  # Last modification date
    
    # Classification
    themes: List[str]            # Theme URIs (e.g., Wikidata concepts)
    theme_labels: List[str]      # Human-readable theme labels
    keywords: List[str]          # Free-text keywords
    
    # Access information
    contact_point: Optional[ContactPoint]  # Contact for data requests
    landing_page: Optional[str]  # URL to dataset landing page
    
    # Parent references
    catalog_uri: str             # Parent catalog URI
    fdp_uri: str                 # Parent FDP URI
    fdp_title: str               # Parent FDP title (for display)
    
    # Distributions (for reference, not used in PoC)
    distributions: List[str]     # URIs of distributions
```

**JSON Representation:**
```json
{
  "uri": "https://example.org/fdp/dataset/123",
  "title": "Biodiversity Survey Data 2023",
  "description": "Annual biodiversity survey results...",
  "publisher": "Example University",
  "creator": "Dr. Jane Smith",
  "issued": "2023-06-15",
  "modified": "2023-12-01",
  "themes": ["http://www.wikidata.org/entity/Q47041"],
  "theme_labels": ["Biodiversity"],
  "keywords": ["ecology", "species", "survey"],
  "contact_point": {
    "name": "Data Steward",
    "email": "data@example.org"
  },
  "landing_page": "https://example.org/datasets/biodiversity-2023",
  "catalog_uri": "https://example.org/fdp/catalog/1",
  "fdp_uri": "https://example.org/fdp",
  "fdp_title": "Example FAIR Data Point",
  "distributions": []
}
```

---

### 4. ContactPoint

Represents contact information for a dataset.

```python
@dataclass
class ContactPoint:
    """Contact information for data requests."""
    
    name: Optional[str]          # Contact name or role
    email: Optional[str]         # Email address
    url: Optional[str]           # Contact form URL (alternative to email)
```

**JSON Representation:**
```json
{
  "name": "Research Data Team",
  "email": "data-requests@example.org",
  "url": null
}
```

---

### 5. DataRequest

Represents a data access request being composed by the user.

```python
@dataclass
class DataRequest:
    """A data access request being composed."""
    
    # Requester information
    requester_name: str          # Full name of requester
    requester_email: str         # Email address
    requester_affiliation: str   # Organization/institution
    requester_orcid: Optional[str]  # ORCID identifier (optional)
    
    # Request details
    datasets: List[DatasetReference]  # Datasets being requested
    query: str                   # The query/analysis to be performed
    purpose: str                 # Purpose/justification
    output_constraints: Optional[str]  # Constraints on output format
    timeline: Optional[str]      # Urgency/timeline information
    
    # Metadata
    created_at: datetime         # When request was started
    
    
@dataclass
class DatasetReference:
    """Minimal dataset info for request composition."""
    
    uri: str                     # Dataset URI
    title: str                   # Dataset title
    contact_email: str           # Contact email for this dataset
    fdp_title: str               # Source FDP name
```

**JSON Representation:**
```json
{
  "requester_name": "Dr. John Doe",
  "requester_email": "j.doe@university.edu",
  "requester_affiliation": "University of Example",
  "requester_orcid": "0000-0002-1234-5678",
  "datasets": [
    {
      "uri": "https://example.org/fdp/dataset/123",
      "title": "Biodiversity Survey Data 2023",
      "contact_email": "data@example.org",
      "fdp_title": "Example FAIR Data Point"
    }
  ],
  "query": "SELECT species, count FROM observations WHERE year = 2023",
  "purpose": "Analysis of species distribution patterns for conservation planning",
  "output_constraints": "Aggregated results only, minimum cell size of 5",
  "timeline": "Results needed within 4 weeks",
  "created_at": "2024-01-20T14:30:00Z"
}
```

---

## Service Interfaces

### FDPClient Interface

```python
class FDPClient:
    """Client for fetching and parsing FAIR Data Point metadata."""
    
    def fetch_fdp(self, uri: str) -> FairDataPoint:
        """
        Fetch and parse FDP metadata.
        
        Args:
            uri: The FDP endpoint URL
            
        Returns:
            FairDataPoint with metadata and catalog URIs
            
        Raises:
            FDPConnectionError: If FDP is unreachable
            FDPParseError: If RDF cannot be parsed
        """
        pass
    
    def fetch_catalog(self, uri: str, fdp_uri: str) -> Catalog:
        """
        Fetch and parse a catalog from an FDP.
        
        Args:
            uri: The catalog URI
            fdp_uri: The parent FDP URI
            
        Returns:
            Catalog with dataset URIs
        """
        pass
    
    def fetch_dataset(self, uri: str, catalog_uri: str, 
                      fdp_uri: str, fdp_title: str) -> Dataset:
        """
        Fetch and parse dataset metadata.
        
        Args:
            uri: The dataset URI
            catalog_uri: Parent catalog URI
            fdp_uri: Parent FDP URI
            fdp_title: Parent FDP title for display
            
        Returns:
            Dataset with full metadata
        """
        pass
    
    def discover_fdps_from_index(self, index_uri: str) -> List[str]:
        """
        Extract linked FDP URIs from an index FDP.
        
        Args:
            index_uri: URI of the index FDP
            
        Returns:
            List of discovered FDP URIs
        """
        pass
```

---

### DatasetService Interface

```python
class DatasetService:
    """Service for aggregating and filtering datasets."""
    
    def get_all_datasets(self, fdp_uris: List[str]) -> List[Dataset]:
        """
        Fetch all datasets from the given FDPs.
        
        Args:
            fdp_uris: List of FDP URIs to fetch from
            
        Returns:
            List of all datasets
        """
        pass
    
    def filter_by_theme(self, datasets: List[Dataset], 
                        theme_uri: str) -> List[Dataset]:
        """Filter datasets by theme URI."""
        pass
    
    def filter_by_keyword(self, datasets: List[Dataset], 
                          keyword: str) -> List[Dataset]:
        """Filter datasets containing keyword in title/description/keywords."""
        pass
    
    def search(self, datasets: List[Dataset], 
               query: str) -> List[Dataset]:
        """
        Full-text search across dataset metadata.
        
        Args:
            datasets: Datasets to search
            query: Search query string
            
        Returns:
            Matching datasets, ordered by relevance
        """
        pass
    
    def get_available_themes(self, datasets: List[Dataset]) -> List[Theme]:
        """
        Extract unique themes from datasets for filter UI.
        
        Returns:
            List of Theme objects with uri and label
        """
        pass
```

---

### EmailComposer Interface

```python
class EmailComposer:
    """Service for composing data access request emails."""
    
    def compose_request_email(self, request: DataRequest) -> ComposedEmail:
        """
        Generate the email text for a data request.
        
        Args:
            request: The completed data request
            
        Returns:
            ComposedEmail with subject, body, and recipients
        """
        pass
    
    def group_by_contact(self, request: DataRequest) -> Dict[str, List[DatasetReference]]:
        """
        Group datasets by contact email for sending.
        
        Returns:
            Dict mapping email addresses to datasets
        """
        pass


@dataclass
class ComposedEmail:
    """A composed email ready for sending/display."""
    
    recipients: List[str]        # To: addresses
    subject: str                 # Email subject line
    body: str                    # Plain text email body
```

---

## Email Template Structure

The email body follows this structure:

```
Subject: Data Access Request - [Dataset Title(s)]

Dear Data Steward,

I am writing to request access to data for analysis under a data visiting arrangement.

== REQUESTER INFORMATION ==
Name: [requester_name]
Email: [requester_email]
Affiliation: [requester_affiliation]
ORCID: [requester_orcid] (if provided)

== REQUESTED DATASETS ==
1. [dataset_title]
   URI: [dataset_uri]
   Source: [fdp_title]

2. [additional datasets...]

== PROPOSED QUERY ==
[query]

== PURPOSE / JUSTIFICATION ==
[purpose]

== OUTPUT CONSTRAINTS ==
[output_constraints] (if provided)

== TIMELINE ==
[timeline] (if provided)

I understand that the query will be executed locally on your systems and only 
verified/approved results will be returned. Please let me know if you require 
any additional information or documentation.

Thank you for considering this request.

Best regards,
[requester_name]
[requester_affiliation]
```

---

## RDF Namespaces

Standard namespaces used for parsing FDP metadata:

```python
NAMESPACES = {
    'dcat': 'http://www.w3.org/ns/dcat#',
    'dct': 'http://purl.org/dc/terms/',
    'foaf': 'http://xmlns.com/foaf/0.1/',
    'vcard': 'http://www.w3.org/2006/vcard/ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'fdp': 'https://w3id.org/fdp/fdp-o#',
    'ldp': 'http://www.w3.org/ns/ldp#',
}
```

---

## Error Types

```python
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
```
