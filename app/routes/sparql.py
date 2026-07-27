"""SPARQL query execution routes."""

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    flash,
    redirect,
    url_for,
)

from app.routes.auth import login_required
from app.routes.datasets import sync_discovered_endpoints
from app.services import SPARQLClient
from app.models import SPARQLQuery, EndpointCredentials
from app.config import Config


sparql_bp = Blueprint('sparql', __name__, url_prefix='/sparql')


def _get_selection_endpoints() -> list:
    """Get SPARQL endpoints from datasets currently in the selection."""
    sync_discovered_endpoints()
    selection = session.get('selection', [])
    discovered = session.get('discovered_endpoints', {})
    endpoint_credentials = session.get('endpoint_credentials', {})
    login_username = session.get('user', {}).get('username', '')
    hide_sandbox = login_username != 'sandbox_query'

    if not selection or not discovered:
        return []

    selection_uris = {item['uri'] for item in selection}
    endpoints = []
    seen_urls = set()

    for ep_hash, ep in discovered.items():
        # Only include endpoints whose source dataset is in the selection
        if ep.get('dataset_uri') not in selection_uris:
            continue
        # Sandbox endpoints are only visible in the sandbox environment.
        if hide_sandbox and 'sandbox' in (ep.get('dataset_title') or '').lower():
            continue
        endpoint_url = ep.get('endpoint_url', '')
        if endpoint_url in seen_urls:
            continue
        seen_urls.add(endpoint_url)

        # Reflect which credentials this endpoint will authenticate with:
        # a per-endpoint credential if configured, otherwise the login.
        saved = endpoint_credentials.get(ep_hash)
        if saved and saved.get('username'):
            auth_username = saved['username']
            auth_source = 'custom'
        else:
            auth_username = login_username
            auth_source = 'login'

        endpoints.append({
            'hash': ep_hash,
            'endpoint_url': endpoint_url,
            'fdp_title': ep.get('fdp_title', 'Unknown'),
            'dataset_title': ep.get('dataset_title', 'Unknown'),
            'auth_username': auth_username,
            'auth_source': auth_source,
        })

    return endpoints


@sparql_bp.route('/')
@login_required
def index() -> str:
    """SPARQL query landing page.

    Shows endpoints available from selection datasets.

    Returns:
        Rendered SPARQL index template.
    """
    endpoints = _get_selection_endpoints()
    selection = session.get('selection', [])

    return render_template(
        'sparql/index.html',
        endpoints=endpoints,
        selection=selection,
    )


@sparql_bp.route('/query', methods=['GET', 'POST'])
@login_required
def query() -> str:
    """SPARQL query editor and execution.

    Endpoints come from selection datasets. Credentials come from login.

    Returns:
        Rendered query form or redirect to results.
    """
    endpoints = _get_selection_endpoints()

    if not endpoints:
        selection = session.get('selection', [])
        if not selection:
            flash('Your selection is empty. Add datasets with SPARQL endpoints first.', 'warning')
            return redirect(url_for('datasets.browse'))
        else:
            flash(
                'No SPARQL endpoints found in your selection datasets. '
                'View dataset details to discover endpoints, or add datasets that have SPARQL distributions.',
                'warning'
            )
            return redirect(url_for('sparql.index'))

    if request.method == 'POST':
        query_text = request.form.get('query', '').strip()
        selected_hashes = request.form.getlist('endpoints')

        if not query_text:
            flash('Please enter a SPARQL query.', 'error')
            return render_template(
                'sparql/query.html',
                endpoints=endpoints,
                query_text='',
                selected=[],
            )

        if not selected_hashes:
            flash('Please select at least one endpoint.', 'error')
            return render_template(
                'sparql/query.html',
                endpoints=endpoints,
                query_text=query_text,
                selected=[],
            )

        # Remember the selection so 'New Query' restores the same endpoints.
        session['sparql_selected_hashes'] = selected_hashes
        session.modified = True

        # Validate query syntax
        timeout = getattr(Config, 'SPARQL_TIMEOUT', 60)
        client = SPARQLClient(timeout=timeout)
        if not client.validate_query(query_text):
            flash(
                'Invalid SPARQL query. Query must start with SELECT, CONSTRUCT, ASK, or DESCRIBE.',
                'error'
            )
            return render_template(
                'sparql/query.html',
                endpoints=endpoints,
                query_text=query_text,
                selected=selected_hashes,
            )

        # Build execution plan. Per-endpoint credentials (configured under
        # /auth/credentials) take precedence; login credentials are the fallback.
        user = session.get('user', {})
        discovered = session.get('discovered_endpoints', {})
        endpoint_credentials = session.get('endpoint_credentials', {})

        target_endpoints = []
        credentials_map = {}
        fdp_titles = {}

        for ep_hash in selected_hashes:
            ep = discovered.get(ep_hash)
            if not ep:
                continue

            endpoint_url = ep['endpoint_url']
            target_endpoints.append(endpoint_url)
            parts = [ep.get('fdp_title', ''), ep.get('catalog_title', ''), ep.get('dataset_title', '')]
            fdp_titles[endpoint_url] = ' / '.join(p for p in parts if p) or endpoint_url

            # Per-endpoint credentials take precedence; login is the fallback.
            saved = endpoint_credentials.get(ep_hash)
            if saved and saved.get('username'):
                username = saved.get('username', '')
                password = saved.get('password', '')
            else:
                username = user.get('username', '')
                password = user.get('password', '')

            credentials_map[endpoint_url] = EndpointCredentials(
                fdp_uri=ep.get('fdp_uri', ''),
                sparql_endpoint=endpoint_url,
                username=username,
                password=password,
            )

        # Execute federated query
        sparql_query = SPARQLQuery(
            query_text=query_text,
            target_endpoints=target_endpoints,
        )

        result = client.execute_federated(
            sparql_query, credentials_map, fdp_titles
        )

        # Store result in session for display
        session['query_result'] = result.to_dict()
        session.modified = True

        return redirect(url_for('sparql.results'))

    # GET request - show query form, restoring the previous endpoint selection.
    selected = session.get('sparql_selected_hashes', [])
    return render_template(
        'sparql/query.html',
        endpoints=endpoints,
        query_text='',
        selected=selected,
    )


@sparql_bp.route('/results')
@login_required
def results() -> str:
    """Display SPARQL query results.

    Returns:
        Rendered results template or redirect if no results.
    """
    result_data = session.get('query_result')

    if not result_data:
        flash('No query results to display.', 'warning')
        return redirect(url_for('sparql.query'))

    return render_template(
        'sparql/results.html',
        result=result_data,
    )


@sparql_bp.route('/graph-test')
def graph_test() -> str:
    """Standalone graph rendering test page with mock triples."""
    return render_template('sparql/graph_test.html')


@sparql_bp.route('/results/clear', methods=['POST'])
@login_required
def clear_results() -> str:
    """Clear stored query results.

    Returns:
        Redirect to query page.
    """
    session.pop('query_result', None)
    session.modified = True
    flash('Results cleared.', 'success')
    return redirect(url_for('sparql.query'))
