# Data Visiting PoC

A Flask-based web application for discovering datasets across [FAIR Data Points](https://www.fairdatapoint.org/) (FDPs), composing standardized data access request emails, and executing authenticated SPARQL queries.

## Overview

Data visiting (code-to-data) is an approach where queries are sent to datasets for local execution, returning only verified results. This tool handles the **requester** side of that workflow:

1. **Discover** datasets across multiple FAIR Data Points
2. **Browse and filter** datasets by theme, keyword, or free-text search
3. **Compose** standardized data access request emails grouped by contact
4. **Query** SPARQL endpoints discovered from dataset distributions

## Features

### Dataset Discovery
- Add and manage FAIR Data Point endpoints (single or index FDPs)
- Browse datasets with filtering by theme, keyword, and free-text search
- Pagination and sorting for large dataset collections
- Automatic discovery of SPARQL endpoints from DCAT distributions

### Data Access Requests
- Add datasets to a request basket
- Compose data access requests with structured metadata (name, affiliation, ORCID, purpose)
- Automatically group and generate separate emails per dataset contact
- Preview and copy composed request emails

### Authenticated SPARQL Queries
- Log in with credentials for SPARQL endpoint authentication
- Execute read-only SPARQL queries against discovered endpoints
- Client-side query federation across multiple endpoints
- View aggregated results with per-endpoint breakdown

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/RenVit318/FDP-Crawler.git
cd FDP-Crawler

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env .env.local
# Edit .env.local with your settings (especially SECRET_KEY for production)

# Run the application
flask run
```

The application will be available at `http://localhost:5000`.

### Docker

```bash
# Build and run
docker build -t fdp-crawler .
docker run -p 5000:5000 -e SECRET_KEY=your-secret-key fdp-crawler

# Or use docker-compose
docker-compose up
```

## Configuration

Environment variables (set in `.env` or system environment):

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret key | Auto-generated |
| `FDP_TIMEOUT` | Timeout for FDP HTTP requests (seconds) | `30` |
| `SPARQL_TIMEOUT` | Timeout for SPARQL queries (seconds) | `60` |
| `VERIFY_SSL` | Verify SSL certificates for FDP requests | `true` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `FLASK_DEBUG` | Enable Flask debug mode | `false` |

## Usage

### Public Flow (no login required)
1. **Add FDP endpoints** at `/fdp/add` -- supports both single FDPs and index FDPs
2. **Browse datasets** at `/datasets` -- filter by theme, keyword, or search
3. **Add to basket** -- select datasets for your data access request
4. **Compose request** at `/request/compose` -- fill in your details and query description
5. **Preview emails** -- review generated emails and copy them to send

### Authenticated Flow (login required)
1. **Log in** at `/auth/login` with your SPARQL endpoint credentials
2. **Add datasets** with SPARQL endpoints to your basket
3. **View endpoint details** on dataset detail pages to discover SPARQL distributions
4. **Query endpoints** at `/sparql/query` -- write and execute SPARQL SELECT queries
5. **View results** aggregated across selected endpoints

## Testing

```bash
# Run the full test suite
pytest

# Run with coverage
pytest --cov=app

# Run a specific test file
pytest tests/test_fdp_client.py
```

## Project Structure

```
FDP-Crawler/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration from environment
│   ├── utils.py             # Shared utility functions
│   ├── models/              # Dataclasses (FDP, Dataset, Distribution, SPARQL, etc.)
│   ├── services/            # Business logic (FDP client, SPARQL client, email composer)
│   ├── routes/              # Flask blueprints (main, fdp, datasets, request, auth, sparql)
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS and JavaScript
├── tests/
│   ├── fixtures/            # Mock RDF/Turtle data for tests
│   ├── conftest.py          # Shared pytest fixtures
│   └── test_*.py            # Test modules
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container image definition
├── docker-compose.yml       # Container orchestration
└── run.py                   # Application entry point
```

## Security Notes

This application is a **proof of concept** and has known limitations:

- **Session-based storage**: All state (FDPs, datasets, basket, credentials) is stored in server-side filesystem sessions. There is no database.
- **Authentication**: The login system stores credentials in the session for reuse with SPARQL endpoints. It does not implement a user database or password hashing.
- **No CSRF protection**: Forms do not include CSRF tokens. Consider adding [Flask-WTF](https://flask-wtf.readthedocs.io/) for production use.
- **SSRF considerations**: Users can supply arbitrary FDP URLs that the server will fetch. Consider URL validation/allowlisting for production.

For production deployment, you should also:
- Set a strong `SECRET_KEY` via environment variable
- Run behind a reverse proxy (nginx/Caddy) with HTTPS
- Add rate limiting (e.g., [Flask-Limiter](https://flask-limiter.readthedocs.io/))
- Enable `SESSION_COOKIE_SECURE=True` when serving over HTTPS

## License

MIT License -- see [LICENSE](LICENSE) for details.
