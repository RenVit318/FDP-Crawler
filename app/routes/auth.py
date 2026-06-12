"""Authentication routes."""

from functools import wraps
from typing import Callable, Any

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    flash,
    redirect,
    url_for,
)

from app.routes.datasets import sync_discovered_endpoints


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to require login for a route.

    Args:
        f: The route function to wrap.

    Returns:
        Wrapped function that checks for authentication.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not session.get('user'):
            flash('Please log in to access this feature.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
def login() -> str:
    """Handle user login.

    Returns:
        Rendered login template or redirect on success.
    """
    if session.get('user'):
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('auth/login.html')

        # Store credentials — username/password are reused for all SPARQL endpoints
        session['user'] = {
            'username': username,
            'password': password,
            'is_authenticated': True,
        }
        session.modified = True

        flash(f'Welcome, {username}!', 'success')

        # Redirect to next page or home (block protocol-relative URLs)
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/') and not next_page.startswith('//'):
            return redirect(next_page)
        return redirect(url_for('main.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
def logout() -> str:
    """Handle user logout.

    Returns:
        Redirect to home page.
    """
    username = session.get('user', {}).get('username', 'User')

    # Clear user-related session data
    session.pop('user', None)
    session.pop('endpoint_credentials', None)
    session.pop('query_result', None)
    session.modified = True

    flash(f'Goodbye, {username}!', 'success')
    return redirect(url_for('main.index'))


@auth_bp.route('/credentials')
@login_required
def list_credentials() -> str:
    """List configured endpoint credentials and discovered endpoints."""
    sync_discovered_endpoints()
    credentials = session.get('endpoint_credentials', {})
    discovered_endpoints = session.get('discovered_endpoints', {})
    return render_template(
        'auth/credentials.html',
        credentials=credentials,
        discovered_endpoints=discovered_endpoints,
    )


@auth_bp.route('/credentials/<fdp_hash>', methods=['GET', 'POST'])
@login_required
def configure_credentials(fdp_hash: str) -> str:
    """Configure credentials for a discovered SPARQL endpoint."""
    discovered_ep = session.get('discovered_endpoints', {}).get(fdp_hash)
    existing = session.get('endpoint_credentials', {}).get(fdp_hash, {})

    if not discovered_ep and not existing:
        flash('Endpoint not found.', 'error')
        return redirect(url_for('auth.list_credentials'))

    if discovered_ep:
        fdp = {
            'uri': discovered_ep['fdp_uri'],
            'title': discovered_ep['fdp_title'],
            'description': f"Discovered from dataset: {discovered_ep['dataset_title']}",
        }
        pre_filled_endpoint = discovered_ep['endpoint_url']
    else:
        fdp = {
            'uri': existing.get('fdp_uri', ''),
            'title': existing.get('sparql_endpoint', 'Configured endpoint'),
            'description': None,
        }
        pre_filled_endpoint = existing.get('sparql_endpoint', '')

    if request.method == 'POST':
        sparql_endpoint = request.form.get('sparql_endpoint', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not sparql_endpoint:
            flash('SPARQL endpoint URL is required.', 'error')
            return render_template(
                'auth/configure_credentials.html',
                fdp=fdp,
                fdp_hash=fdp_hash,
                existing=existing,
                pre_filled_endpoint=pre_filled_endpoint,
            )

        # Preserve existing password if not provided
        if not password and existing.get('password'):
            password = existing['password']

        # Store credentials in session
        if 'endpoint_credentials' not in session:
            session['endpoint_credentials'] = {}

        session['endpoint_credentials'][fdp_hash] = {
            'fdp_uri': fdp['uri'],
            'sparql_endpoint': sparql_endpoint,
            'username': username,
            'password': password,
        }
        session.modified = True

        flash(f'Credentials saved for {fdp["title"]}', 'success')
        return redirect(url_for('auth.list_credentials'))

    return render_template(
        'auth/configure_credentials.html',
        fdp=fdp,
        fdp_hash=fdp_hash,
        existing=existing,
        pre_filled_endpoint=pre_filled_endpoint,
    )


@auth_bp.route('/credentials/<fdp_hash>/remove', methods=['POST'])
@login_required
def remove_credentials(fdp_hash: str) -> str:
    """Remove credentials for an FDP endpoint.

    Args:
        fdp_hash: The MD5 hash of the FDP URI.

    Returns:
        Redirect to credentials list.
    """
    credentials = session.get('endpoint_credentials', {})

    if fdp_hash in credentials:
        del credentials[fdp_hash]
        session['endpoint_credentials'] = credentials
        session.modified = True
        flash('Credentials removed.', 'success')
    else:
        flash('No credentials found for this endpoint.', 'warning')

    return redirect(url_for('auth.list_credentials'))
