# Data Visiting PoC

A Flask-based web application for discovering datasets across FAIR Data Points (FDPs) and composing standardized data access request emails.

## Overview

Data visiting (code-to-data) is an approach where queries are sent to datasets for local execution, returning only verified results. This tool handles the "requester" side of that workflow:

1. **Discover** datasets across multiple FAIR Data Points
2. **Browse and filter** datasets by theme, keyword, or free-text search
3. **Compose** standardized data access request emails
4. **Send** requests to dataset contact points

## Features

- Add and manage FAIR Data Point endpoints
- Support for index FDPs that link to multiple FDPs
- Browse datasets with filtering and search
- Compose data access requests with structured metadata
- Generate properly formatted request emails
- Group requests by contact when requesting multiple datasets

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd data-visiting-poc
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. Run the application:
   ```bash
   flask run
   ```

   The application will be available at http://localhost:5000

### Docker

Build and run with Docker:

```bash
docker build -t data-visiting-poc .
docker run -p 8080:5000 data-visiting-poc
```

Or use docker-compose:

```bash
docker-compose up
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment (development/production) | development |
| `SECRET_KEY` | Flask session secret key | (generated) |
| `FDP_TIMEOUT` | Timeout for FDP requests (seconds) | 30 |
| `LOG_LEVEL` | Logging verbosity | INFO |

## Usage

1. **Add FDP endpoints**: Navigate to FDPs and add FAIR Data Point URLs
2. **Browse datasets**: View and filter available datasets
3. **Select datasets**: Add datasets to your request basket
4. **Compose request**: Fill in your details and query information
5. **Preview and send**: Review the generated email and copy/send it

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=app
```

## Project Structure

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
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## License

MIT License - see LICENSE file for details.
