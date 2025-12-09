# Data Visiting PoC - Subtask Breakdown

This document contains the implementation subtasks, each designed to be executed independently by a coding agent with access only to CLAUDE.md and the referenced specification documents.

## Execution Order

The subtasks should be executed in this order:

1. Project Setup
2. Data Models
3. Test Fixtures
4. FDP Client - Core
5. FDP Client - Index Discovery
6. Dataset Service
7. Email Composer
8. Flask App Foundation
9. FDP Routes
10. Dataset Routes
11. Request Routes
12. Templates & Styling
13. Docker Configuration
14. Integration Testing

---

## Subtask 1: Project Setup

**Objective**: Create the project skeleton with configuration files.

**Acceptance Criteria**:
- All configuration files created and valid
- Directory structure matches architecture spec
- Virtual environment can be created and dependencies installed

### Prompt

```
Read CLAUDE.md for project instructions.

Create the initial project structure for "data-visiting-poc":

1. Create the directory structure as specified in CLAUDE.md
2. Create requirements.txt with the approved dependencies
3. Create .env.example with all configuration variables
4. Create app/config.py with the Config class
5. Create empty __init__.py files in all Python packages
6. Create a basic README.md explaining the project

Do NOT implement any functionality yet - just the skeleton.

Verify the structure matches what's documented in CLAUDE.md.
```

---

## Subtask 2: Data Models

**Objective**: Implement all data model classes.

**Acceptance Criteria**:
- All models from 02_DATA_MODELS.md implemented as dataclasses
- Type hints on all fields
- JSON serialization works correctly
- Models importable from app.models

### Prompt

```
Read CLAUDE.md for project instructions.
Read 02_DATA_MODELS.md for complete model specifications.

Implement the data models in app/models/:

1. Create app/models/fdp.py with:
   - FairDataPoint dataclass
   - Catalog dataclass
   
2. Create app/models/dataset.py with:
   - Dataset dataclass
   - ContactPoint dataclass
   
3. Create app/models/request.py with:
   - DataRequest dataclass
   - DatasetReference dataclass
   - ComposedEmail dataclass

4. Update app/models/__init__.py to export all models

5. Add a to_dict() method to each dataclass for JSON serialization

All fields, types, and optional markers must match 02_DATA_MODELS.md exactly.
```

---

## Subtask 3: Test Fixtures

**Objective**: Create mock RDF data for testing.

**Acceptance Criteria**:
- Valid Turtle files that can be parsed by rdflib
- Fixtures cover FDP, catalog, and dataset scenarios
- Index FDP fixture includes links to other FDPs

### Prompt

```
Read CLAUDE.md for project instructions.
Read 02_DATA_MODELS.md for the RDF namespaces section.

Create test fixtures in tests/fixtures/:

1. Create fdp_root.ttl:
   - A valid FDP root document
   - Contains metadata (title, description, publisher)
   - Links to one catalog
   
2. Create fdp_catalog.ttl:
   - A valid DCAT Catalog
   - Contains 2-3 dataset references
   - Has themes defined
   
3. Create dataset.ttl:
   - A complete DCAT Dataset
   - Includes all optional fields (themes, keywords, contact)
   - Has a valid vcard:hasEmail contact point
   
4. Create fdp_index.ttl:
   - An index FDP
   - Links to 2 other FDP URIs using fdp:metadataService
   
5. Create tests/conftest.py with pytest fixtures that load these files

Use realistic but fictional data. Ensure all URIs are consistent within the fixtures.
```

---

## Subtask 4: FDP Client - Core

**Objective**: Implement basic FDP fetching and parsing.

**Acceptance Criteria**:
- Can fetch and parse FDP metadata
- Can fetch and parse catalogs
- Can fetch and parse datasets with contact points
- Proper error handling with custom exceptions
- All tests pass

### Prompt

```
Read CLAUDE.md for project instructions.
Read 02_DATA_MODELS.md for model specs and interface definitions.

Implement the core FDP client in app/services/fdp_client.py:

1. Create custom exception classes:
   - FDPError (base)
   - FDPConnectionError
   - FDPParseError
   - FDPTimeoutError

2. Implement FDPClient class with:
   - __init__(self, timeout: int = 30)
   - fetch_fdp(self, uri: str) -> FairDataPoint
   - fetch_catalog(self, uri: str, fdp_uri: str) -> Catalog
   - fetch_dataset(self, uri: str, catalog_uri: str, fdp_uri: str, fdp_title: str) -> Dataset
   
3. Private helper methods:
   - _fetch_rdf(self, uri: str) -> Graph
   - _extract_contact_point(self, graph: Graph, dataset_uri: URIRef) -> Optional[ContactPoint]

4. Write tests in tests/test_fdp_client.py:
   - Test successful fetch and parse for each method
   - Test error handling (connection error, parse error, timeout)
   - Use the fixtures and responses library to mock HTTP

Follow the implementation guidelines in CLAUDE.md for content negotiation and error handling.
```

---

## Subtask 5: FDP Client - Index Discovery

**Objective**: Add support for index FDPs that link to other FDPs.

**Acceptance Criteria**:
- Can identify if an FDP is an index
- Can extract linked FDP URIs from index
- Recursive discovery works (index → FDPs → catalogs → datasets)
- Tests cover index scenarios

### Prompt

```
Read CLAUDE.md for project instructions.
Read 02_DATA_MODELS.md for model specs.

Extend the FDP client in app/services/fdp_client.py:

1. Add method to FDPClient:
   - discover_fdps_from_index(self, index_uri: str) -> List[str]
   
2. Update fetch_fdp() to:
   - Detect if FDP is an index (has fdp:metadataService links)
   - Set is_index=True and populate linked_fdps if so
   
3. Add convenience method:
   - fetch_all_from_index(self, index_uri: str) -> List[FairDataPoint]
   - Fetches the index, discovers linked FDPs, fetches each one

4. Add tests in tests/test_fdp_client.py:
   - Test index detection
   - Test FDP discovery from index
   - Test fetch_all_from_index
   - Use fdp_index.ttl fixture

Handle errors gracefully - if one linked FDP fails, continue with others and log the error.
```

---

## Subtask 6: Dataset Service

**Objective**: Implement dataset aggregation and filtering.

**Acceptance Criteria**:
- Can aggregate datasets from multiple FDPs
- Filtering by theme and keyword works
- Search function works across metadata fields
- Theme extraction for filter UI works
- All tests pass

### Prompt

```
Read CLAUDE.md for project instructions.
Read 02_DATA_MODELS.md for the DatasetService interface.

Implement app/services/dataset_service.py:

1. Create helper dataclass:
   - Theme(uri: str, label: str, count: int)

2. Implement DatasetService class with:
   - __init__(self, fdp_client: FDPClient)
   - get_all_datasets(self, fdp_uris: List[str]) -> List[Dataset]
   - filter_by_theme(self, datasets: List[Dataset], theme_uri: str) -> List[Dataset]
   - filter_by_keyword(self, datasets: List[Dataset], keyword: str) -> List[Dataset]
   - search(self, datasets: List[Dataset], query: str) -> List[Dataset]
   - get_available_themes(self, datasets: List[Dataset]) -> List[Theme]

3. Search should:
   - Search across title, description, and keywords
   - Be case-insensitive
   - Return results ordered by relevance (title match > description match > keyword match)

4. Write tests in tests/test_dataset_service.py:
   - Test each filter method
   - Test search with various queries
   - Test theme extraction
   - Mock the FDP client

All filter/search functions should be pure - they take a list and return a filtered list.
```

---

## Subtask 7: Email Composer

**Objective**: Implement email composition from data requests.

**Acceptance Criteria**:
- Generates properly formatted email text
- Groups datasets by contact email
- All request fields included in output
- Handles optional fields gracefully
- Tests verify output format

### Prompt

```
Read CLAUDE.md for project instructions.
Read 02_DATA_MODELS.md for the EmailComposer interface and email template structure.

Implement app/services/email_composer.py:

1. Implement EmailComposer class with:
   - compose_request_email(self, request: DataRequest) -> ComposedEmail
   - group_by_contact(self, request: DataRequest) -> Dict[str, List[DatasetReference]]

2. Email composition rules:
   - Subject: "Data Access Request - [first dataset title]" (add "+ N more" if multiple)
   - Body must follow the template structure in 02_DATA_MODELS.md exactly
   - Optional fields should be omitted entirely if not provided (not shown as "N/A")
   - Multiple datasets should be numbered in the body

3. When datasets have different contacts:
   - group_by_contact() returns dict mapping email -> datasets
   - compose_request_email() should handle this by either:
     a) Generating separate emails per contact, or
     b) Listing all datasets but noting different contacts
   - Implement option (a) for this PoC

4. Write tests in tests/test_email_composer.py:
   - Test single dataset request
   - Test multiple datasets, same contact
   - Test multiple datasets, different contacts
   - Test with all optional fields
   - Test with no optional fields
   - Verify email structure matches template

Update app/services/__init__.py to export EmailComposer.
```

---

## Subtask 8: Flask App Foundation

**Objective**: Create the Flask application factory and base templates.

**Acceptance Criteria**:
- App factory creates working Flask app
- Base template provides consistent layout
- Static files served correctly
- Flash messages display properly
- App runs without errors

### Prompt

```
Read CLAUDE.md for project instructions.

Create the Flask application foundation:

1. Implement app/__init__.py:
   - create_app(config_override=None) factory function
   - Register blueprints (create empty blueprint modules for now)
   - Configure logging
   - Initialize session

2. Create app/templates/base.html:
   - HTML5 document structure
   - Navigation header with links: Home, FDPs, Datasets, Request
   - Flash message display area
   - Content block for child templates
   - Footer with project info
   - Link to static/css/style.css

3. Create app/templates/index.html:
   - Extends base.html
   - Welcome message explaining the tool
   - Quick start steps
   - Links to add FDP and browse datasets

4. Create app/static/css/style.css:
   - Clean, minimal styling
   - Responsive layout (mobile-friendly)
   - Styles for: navigation, forms, buttons, flash messages, cards

5. Create app/static/js/main.js:
   - Empty for now, placeholder for future interactions

6. Create app/routes/main.py:
   - Blueprint: main_bp
   - Route: / -> renders index.html

7. Create empty blueprint files (just the Blueprint object):
   - app/routes/fdp.py (fdp_bp)
   - app/routes/datasets.py (datasets_bp)  
   - app/routes/request.py (request_bp)

Verify the app starts with: flask run
```

---

## Subtask 9: FDP Routes

**Objective**: Implement FDP management routes and templates.

**Acceptance Criteria**:
- Can view list of configured FDPs
- Can add new FDP by URL
- Can add index FDP and discover linked FDPs
- Can refresh FDP metadata
- Error states displayed clearly

### Prompt

```
Read CLAUDE.md for project instructions.

Implement FDP management routes:

1. Update app/routes/fdp.py with routes:
   - GET /fdp -> list all configured FDPs
   - GET /fdp/add -> show add FDP form
   - POST /fdp/add -> process add FDP form
   - POST /fdp/<uri_hash>/refresh -> refresh single FDP metadata
   - POST /fdp/<uri_hash>/remove -> remove FDP from list

2. FDP storage:
   - Store FDPs in Flask session for this PoC
   - Use MD5 hash of URI as identifier

3. Add form handling:
   - URL input with validation
   - Checkbox: "This is an index FDP"
   - If index, automatically discover and add linked FDPs

4. Create templates:
   - app/templates/fdp/list.html
     - Show all FDPs with status indicators
     - Show catalog count for each
     - Refresh and remove buttons
     - "Add FDP" button
   
   - app/templates/fdp/add.html
     - Form with URL input
     - Index checkbox
     - Submit and cancel buttons

5. Error handling:
   - Show flash messages for connection errors
   - Show inline validation errors
   - Gracefully handle partial failures (some FDPs work, some don't)

Integrate with FDPClient service.
```

---

## Subtask 10: Dataset Routes

**Objective**: Implement dataset browsing and filtering.

**Acceptance Criteria**:
- Can browse all datasets from configured FDPs
- Can filter by theme
- Can search by keyword
- Can view dataset details
- Dataset selection for requests works

### Prompt

```
Read CLAUDE.md for project instructions.

Implement dataset browsing routes:

1. Update app/routes/datasets.py with routes:
   - GET /datasets -> browse all datasets with filters
   - GET /datasets/search?q=<query> -> search datasets
   - GET /dataset/<uri_hash> -> dataset detail view

2. Dataset listing features:
   - Fetch datasets from all configured FDPs
   - Theme filter dropdown (populated from available themes)
   - Keyword search box
   - Pagination (10 per page for PoC)
   - Sort by: title, date modified, FDP

3. Create templates:
   - app/templates/datasets/browse.html
     - Filter sidebar (themes, search)
     - Dataset cards showing: title, description snippet, FDP source, themes
     - "Add to request" button on each card
     - Pagination controls
   
   - app/templates/datasets/detail.html
     - Full metadata display
     - Contact information
     - Link to source FDP
     - "Add to request" button

4. Session-based dataset caching:
   - Cache fetched datasets in session
   - Add "Refresh datasets" button to force re-fetch

5. Request basket:
   - Store selected dataset URIs in session
   - Show basket count in navigation
   - "Add to request" toggles selection

Integrate with DatasetService.
```

---

## Subtask 11: Request Routes

**Objective**: Implement request composition workflow.

**Acceptance Criteria**:
- Can view selected datasets in basket
- Can fill request form with all fields
- Can preview composed email
- Can copy email to clipboard
- Can remove items from basket

### Prompt

```
Read CLAUDE.md for project instructions.
Read 02_DATA_MODELS.md for DataRequest fields and email template.

Implement request composition routes:

1. Update app/routes/request.py with routes:
   - GET /request -> view current basket
   - POST /request/add/<uri_hash> -> add dataset to basket
   - POST /request/remove/<uri_hash> -> remove from basket
   - POST /request/clear -> clear basket
   - GET /request/compose -> show request form
   - POST /request/compose -> process form, show preview
   - GET /request/preview -> display composed email(s)

2. Request basket (session-based):
   - Store list of DatasetReference objects
   - Show dataset count in nav badge
   - Basket view shows all selected datasets with remove option

3. Create templates:
   - app/templates/request/basket.html
     - List selected datasets
     - Remove button for each
     - "Compose Request" button (disabled if empty)
     - "Clear All" button
   
   - app/templates/request/compose.html
     - Form fields:
       - Requester name (required)
       - Requester email (required)
       - Affiliation (required)
       - ORCID (optional)
       - Query (required, textarea)
       - Purpose (required, textarea)
       - Output constraints (optional, textarea)
       - Timeline (optional)
     - Show selected datasets (read-only)
     - Submit and back buttons
   
   - app/templates/request/preview.html
     - Display composed email(s) in styled boxes
     - If multiple contacts: show separate emails
     - "Copy to clipboard" button for each
     - "Edit" button to go back
     - mailto: link as alternative

4. Clipboard functionality:
   - Add JavaScript to copy email text
   - Show confirmation toast on copy

Integrate with EmailComposer service.
```

---

## Subtask 12: Templates & Styling Polish

**Objective**: Refine UI/UX and ensure consistent styling.

**Acceptance Criteria**:
- Consistent visual style across all pages
- Good mobile responsiveness
- Clear error and success states
- Accessible (proper labels, contrast)
- Professional appearance

### Prompt

```
Read CLAUDE.md for project instructions.

Polish the templates and styling:

1. Review and update app/static/css/style.css:
   - Consistent color scheme (suggest professional blues/grays)
   - Typography: readable fonts, proper hierarchy
   - Spacing: consistent padding/margins
   - Form styling: clear inputs, focus states
   - Button styles: primary, secondary, danger variants
   - Card components for datasets/FDPs
   - Status badges (active, error, pending)
   - Responsive breakpoints

2. Update base.html:
   - Improve navigation layout
   - Add request basket badge/counter
   - Better flash message styling with dismiss button
   - Loading indicator for AJAX operations

3. Enhance browse.html:
   - Better filter layout
   - Dataset card hover effects
   - Clear empty state message
   - Visual indication of selected datasets

4. Enhance preview.html:
   - Email displayed in monospace/preformatted
   - Clear visual separation between multiple emails
   - Prominent copy button
   - Success feedback on copy

5. Add to main.js:
   - Flash message auto-dismiss
   - Copy to clipboard function
   - Loading state management
   - Form validation feedback

6. Accessibility improvements:
   - Proper form labels
   - ARIA attributes where needed
   - Sufficient color contrast
   - Keyboard navigation support

Test on mobile viewport sizes.
```

---

## Subtask 13: Docker Configuration

**Objective**: Containerize the application.

**Acceptance Criteria**:
- Dockerfile builds successfully
- Container runs the Flask app
- docker-compose provides easy startup
- Environment variables properly passed
- Container is reasonably sized

### Prompt

```
Read CLAUDE.md for project instructions.

Create Docker configuration:

1. Create Dockerfile:
   - Base: python:3.11-slim
   - Install dependencies from requirements.txt
   - Copy application code
   - Set environment variables
   - Expose port 5000
   - Run with gunicorn (add to requirements.txt - this is approved)
   - Non-root user for security

2. Create docker-compose.yml:
   - Single service: web
   - Build from Dockerfile
   - Port mapping: 8080:5000
   - Environment variables from .env
   - Volume mount for development (optional)
   - Restart policy

3. Create .dockerignore:
   - __pycache__
   - *.pyc
   - .env
   - .git
   - tests/
   - *.md (except README)
   - venv/

4. Update requirements.txt:
   - Add: gunicorn>=21.0.0

5. Create startup script (optional):
   - scripts/start.sh for container entrypoint
   - Handle graceful shutdown

6. Update README.md:
   - Docker build instructions
   - Docker run instructions
   - Environment variable documentation

Test:
- docker build -t data-visiting-poc .
- docker run -p 8080:5000 data-visiting-poc
- Verify app accessible at localhost:8080
```

---

## Subtask 14: Integration Testing

**Objective**: Verify all components work together.

**Acceptance Criteria**:
- Full workflow test passes
- Error scenarios handled gracefully
- Performance acceptable (< 5s page loads)
- No console errors in browser

### Prompt

```
Read CLAUDE.md for project instructions.

Create integration tests and verify the system:

1. Create tests/test_integration.py:
   - Test: Add FDP -> fetch metadata -> verify displayed
   - Test: Browse datasets -> filter -> verify results
   - Test: Select datasets -> compose request -> verify email
   - Test: Full workflow end-to-end

2. Create tests/test_routes.py:
   - Test each route returns correct status codes
   - Test form submissions
   - Test error handling (invalid FDP URL, etc.)

3. Manual testing checklist (document results):
   - [ ] Add a real FDP (e.g., https://fdp.lumc.nl/)
   - [ ] Verify datasets load
   - [ ] Test theme filtering
   - [ ] Test keyword search
   - [ ] Select multiple datasets
   - [ ] Fill request form
   - [ ] Verify email format
   - [ ] Test copy to clipboard
   - [ ] Test on mobile viewport
   - [ ] Test with no FDPs configured
   - [ ] Test with invalid FDP URL

4. Performance check:
   - Measure time to fetch datasets from 3 FDPs
   - Identify any obvious bottlenecks
   - Document findings

5. Create TESTING.md:
   - How to run tests
   - Manual test checklist
   - Known issues/limitations

Report any bugs found with:
- Steps to reproduce
- Expected behavior
- Actual behavior
```

---

## Integration Checkpoints

After completing subtasks, verify integration at these points:

### Checkpoint A (After Subtask 6)
- FDP Client can fetch from test fixtures
- Dataset Service can filter mock data
- All service-level tests pass

### Checkpoint B (After Subtask 11)
- Full Flask app runs
- All routes accessible
- Can navigate between pages
- Session state persists

### Checkpoint C (After Subtask 13)
- Docker container builds
- App runs in container
- Accessible from host machine

### Final Checkpoint (After Subtask 14)
- Complete workflow functional
- Tests pass
- Documentation complete