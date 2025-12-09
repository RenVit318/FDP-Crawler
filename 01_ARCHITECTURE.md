# Data Visiting PoC - Architecture Overview

## Project Summary

A Flask-based web application enabling researchers to discover datasets across FAIR Data Points (FDPs) and compose standardized data access request emails. This is the "requester" component of a data visiting framework where queries are sent to data holders for local execution.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Flask Application                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Routes    │  │  Templates  │  │      Static Assets      │  │
│  │  (views)    │  │   (Jinja2)  │  │     (CSS/JS)            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Core Services                             ││
│  │  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐  ││
│  │  │  FDP Client   │  │Dataset Service│  │ Email Composer  │  ││
│  │  │ (RDF parsing) │  │  (filtering)  │  │  (templating)   │  ││
│  │  └───────────────┘  └───────────────┘  └─────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   External FAIR Data Points                      │
│         (DCAT metadata via RDF/Turtle/JSON-LD)                  │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
data-visiting-poc/
│
├── CLAUDE.md                    # Instructions for coding agent
├── README.md                    # Project documentation
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container definition
├── docker-compose.yml           # Container orchestration
├── .env.example                 # Environment variable template
│
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration management
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── fdp.py               # FDP and Catalog data classes
│   │   ├── dataset.py           # Dataset data class
│   │   └── request.py           # DataRequest data class
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── fdp_client.py        # FDP fetching and RDF parsing
│   │   ├── dataset_service.py   # Dataset filtering and search
│   │   └── email_composer.py    # Email template generation
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py              # Home and general routes
│   │   ├── fdp.py               # FDP management routes
│   │   ├── datasets.py          # Dataset browsing routes
│   │   └── request.py           # Request composition routes
│   │
│   ├── templates/
│   │   ├── base.html            # Base template with layout
│   │   ├── index.html           # Landing page
│   │   ├── fdp/
│   │   │   ├── list.html        # List configured FDPs
│   │   │   └── add.html         # Add new FDP
│   │   ├── datasets/
│   │   │   ├── browse.html      # Browse/filter datasets
│   │   │   └── detail.html      # Dataset detail view
│   │   └── request/
│   │       ├── compose.html     # Compose request form
│   │       └── preview.html     # Preview email before sending
│   │
│   └── static/
│       ├── css/
│       │   └── style.css        # Custom styles
│       └── js/
│           └── main.js          # Client-side interactions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── fixtures/                # Mock RDF data
│   │   ├── fdp_index.ttl        # Sample index FDP
│   │   ├── fdp_catalog.ttl      # Sample catalog
│   │   └── dataset.ttl          # Sample dataset metadata
│   ├── test_fdp_client.py
│   ├── test_dataset_service.py
│   └── test_email_composer.py
│
└── scripts/
    └── init_db.py               # Initialize any persistent storage (future)
```

## Core Components

### 1. FDP Client (`app/services/fdp_client.py`)
Responsible for:
- Fetching RDF metadata from FDP endpoints
- Parsing DCAT structures (Catalog, Dataset, Distribution)
- Handling index FDPs (discovering linked FDPs)
- Content negotiation (Turtle, JSON-LD, RDF/XML)

### 2. Dataset Service (`app/services/dataset_service.py`)
Responsible for:
- Aggregating datasets from multiple FDPs
- Filtering by theme, keyword, publisher
- Full-text search across metadata
- Caching dataset information in session

### 3. Email Composer (`app/services/email_composer.py`)
Responsible for:
- Generating standardized request emails
- Template-based composition
- Collecting contact points from dataset metadata

## Request Flow

1. **User adds FDP endpoints** → Stored in session/config
2. **System fetches metadata** → FDP Client parses RDF
3. **User browses datasets** → Dataset Service filters/searches
4. **User selects datasets** → Added to request basket
5. **User fills request form** → Requester info, query, purpose
6. **System generates email** → Email Composer creates text
7. **User copies/sends email** → To dataset contact points

## Technology Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Web Framework | Flask | Lightweight, well-known, good for PoC |
| RDF Parsing | rdflib | Standard Python RDF library |
| Templating | Jinja2 | Included with Flask |
| HTTP Client | requests | Simple, reliable |
| Container | Docker | Deployment portability |

## Configuration

The application uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment (development/production) | development |
| `SECRET_KEY` | Flask session secret | (generated) |
| `FDP_TIMEOUT` | Timeout for FDP requests (seconds) | 30 |
| `LOG_LEVEL` | Logging verbosity | INFO |

## Future Considerations (Out of Scope for PoC)

- SMTP integration for direct email sending
- Persistent storage (database) for FDP configurations
- User authentication via Verifiable Credentials
- Query template library
- Response tracking and status updates
