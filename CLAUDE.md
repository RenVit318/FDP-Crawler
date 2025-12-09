# CLAUDE.md - Coding Agent Instructions

## Project Overview

You are working on **Data Visiting PoC**, a Flask-based web application for discovering datasets across FAIR Data Points and composing standardized data access request emails.

**Core concept**: Data visiting (code-to-data) sends queries to datasets for local execution, returning only verified results. This tool handles the "requester" side: discovery and request composition.

## Critical Rules

### 1. Package Management
- **DO NOT** install any Python packages without explicit approval from the user
- The approved packages are listed in `requirements.txt`
- If you believe an additional package is needed, STOP and explain why before proceeding

### 2. Code Style
- Follow PEP 8 conventions
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions focused and under 50 lines where possible
- Prefer explicit over implicit

### 3. Architecture Compliance
- Follow the directory structure defined in `01_ARCHITECTURE.md`
- Adhere to data models defined in `02_DATA_MODELS.md`
- Do not create files outside the defined structure without approval
- Use the app factory pattern for Flask

### 4. Testing
- Write tests for any service-layer code
- Use pytest fixtures from `tests/conftest.py`
- Use mock data from `tests/fixtures/` for FDP responses
- Do not make live HTTP requests in tests

## Directory Structure Reference

```
data-visiting-poc/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration
│   ├── models/              # Data classes
│   ├── services/            # Business logic
│   ├── routes/              # Flask blueprints
│   ├── templates/           # Jinja2 templates
│   └── static/              # CSS/JS
├── tests/
│   ├── fixtures/            # Mock RDF data
│   └── test_*.py            # Test files
└── [config files]
```

## Approved Dependencies

```
Flask>=3.0.0
rdflib>=7.0.0
requests>=2.31.0
python-dotenv>=1.0.0
```

For testing:
```
pytest>=8.0.0
pytest-flask>=1.3.0
responses>=0.24.0  # For mocking HTTP requests
```

## Data Models

All data models are defined as Python dataclasses in `app/models/`. Reference `02_DATA_MODELS.md` for complete specifications. Key models:

- `FairDataPoint` - FDP endpoint metadata
- `Catalog` - DCAT Catalog
- `Dataset` - DCAT Dataset with contact info
- `DataRequest` - User's data access request
- `ContactPoint` - Contact information

## RDF Namespaces

Use these consistently when parsing RDF:

```python
from rdflib import Namespace

DCAT = Namespace('http://www.w3.org/ns/dcat#')
DCT = Namespace('http://purl.org/dc/terms/')
FOAF = Namespace('http://xmlns.com/foaf/0.1/')
VCARD = Namespace('http://www.w3.org/2006/vcard/ns#')
RDFS = Namespace('http://www.w3.org/2000/01/rdf-schema#')
FDP = Namespace('https://w3id.org/fdp/fdp-o#')
LDP = Namespace('http://www.w3.org/ns/ldp#')
```

## Service Implementation Guidelines

### FDP Client (`app/services/fdp_client.py`)

When fetching FDP metadata:

1. Use content negotiation (Accept header) for RDF formats
2. Try formats in order: `text/turtle`, `application/ld+json`, `application/rdf+xml`
3. Set reasonable timeouts (default: 30 seconds)
4. Handle errors gracefully with custom exception types
5. Parse with rdflib's Graph

```python
# Example pattern for fetching
headers = {'Accept': 'text/turtle, application/ld+json;q=0.9'}
response = requests.get(uri, headers=headers, timeout=self.timeout)
response.raise_for_status()

graph = Graph()
graph.parse(data=response.text, format='turtle')
```

### Dataset Service (`app/services/dataset_service.py`)

- Aggregate datasets from multiple FDPs
- Implement filtering as pure functions on lists
- Cache results appropriately (session-based for PoC)
- Handle missing optional fields gracefully

### Email Composer (`app/services/email_composer.py`)

- Use the email template structure from `02_DATA_MODELS.md`
- Group datasets by contact email when multiple datasets are requested
- Generate plain text emails (no HTML for PoC)
- All fields must be clearly labeled

## Flask Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Landing page |
| `/fdp` | GET | List configured FDPs |
| `/fdp/add` | GET, POST | Add new FDP endpoint |
| `/fdp/<id>/refresh` | POST | Refresh FDP metadata |
| `/datasets` | GET | Browse/filter datasets |
| `/datasets/<uri>` | GET | Dataset detail view |
| `/request/add/<dataset_uri>` | POST | Add dataset to request basket |
| `/request/remove/<dataset_uri>` | POST | Remove from basket |
| `/request/compose` | GET, POST | Compose request form |
| `/request/preview` | GET | Preview composed email |

## Template Guidelines

- Extend `base.html` for all templates
- Use semantic HTML5 elements
- Keep JavaScript minimal (vanilla JS only)
- Style with CSS classes defined in `static/css/style.css`
- Show user-friendly error messages

## Error Handling

Use custom exception classes:

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
```

In routes, catch exceptions and display user-friendly messages:

```python
try:
    fdp = fdp_client.fetch_fdp(uri)
except FDPConnectionError:
    flash('Could not connect to the FAIR Data Point. Please check the URL.', 'error')
except FDPParseError:
    flash('Could not parse the FDP metadata. The endpoint may not be a valid FDP.', 'error')
```

## Configuration

Use environment variables via `python-dotenv`:

```python
# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    FDP_TIMEOUT = int(os.environ.get('FDP_TIMEOUT', 30))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
```

## Testing Patterns

Use fixtures for mock data:

```python
# tests/conftest.py
import pytest
from app import create_app

@pytest.fixture
def app():
    app = create_app({'TESTING': True})
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def sample_fdp_rdf():
    with open('tests/fixtures/fdp_catalog.ttl') as f:
        return f.read()
```

Mock HTTP responses:

```python
import responses

@responses.activate
def test_fetch_fdp(sample_fdp_rdf):
    responses.add(
        responses.GET,
        'https://example.org/fdp',
        body=sample_fdp_rdf,
        content_type='text/turtle'
    )
    # ... test code
```

## Subtask Completion Checklist

Before marking any subtask complete, verify:

- [ ] Code follows PEP 8 and includes type hints
- [ ] All public functions have docstrings
- [ ] No unapproved packages were added
- [ ] Files are in correct locations per architecture
- [ ] Data models match specifications
- [ ] Tests pass (if applicable to subtask)
- [ ] No hardcoded values that should be configurable

## Questions?

If requirements are unclear or you need to deviate from these instructions:

1. STOP before implementing
2. Explain the issue or proposed change
3. Wait for approval before proceeding
