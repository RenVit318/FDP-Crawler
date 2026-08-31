"""Authentication routes."""

import logging
from functools import wraps
from typing import Callable, Any, Optional

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    session,
    flash,
    redirect,
    url_for,
)

from app.routes.datasets import sync_discovered_endpoints
from app.services import keycloak


logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _safe_next(candidate: Optional[str]) -> Optional[str]:
    """Return candidate only if it is a same-site relative path.

    Blocks absolute URLs and protocol-relative ones ("//evil.com"), which the
    browser would treat as external.
    """
    if candidate and candidate.startswith('/') and not candidate.startswith('//'):
        return candidate
    return None


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
            'auth_method': 'password',
        }
        session.modified = True

        flash(f'Welcome, {username}!', 'success')

        # Redirect to next page or home (block protocol-relative URLs)
        next_page = _safe_next(request.args.get('next'))
        if next_page:
            return redirect(next_page)
        return redirect(url_for('main.index'))

    return render_template('auth/login.html')


@auth_bp.route('/keycloak/login')
def keycloak_login() -> str:
    """Start the OIDC authorization-code flow against Keycloak.

    Returns:
        Redirect to Keycloak, or back to the login form when Keycloak is off.
    """
    if not keycloak.is_enabled():
        flash('Keycloak login is not configured on this instance.', 'error')
        return redirect(url_for('auth.login'))

    # Stash the post-login destination: Keycloak returns to a fixed, registered
    # redirect URI, so it cannot carry a ?next through for us.
    next_page = _safe_next(request.args.get('next'))
    if next_page:
        session['keycloak_next'] = next_page
    else:
        session.pop('keycloak_next', None)
    session.modified = True

    redirect_uri = url_for('auth.keycloak_callback', _external=True)
    return keycloak.get_client().authorize_redirect(redirect_uri)


@auth_bp.route('/keycloak/callback')
def keycloak_callback() -> str:
    """Complete the OIDC flow and sign the user in.

    Returns:
        Redirect to the stashed destination, or to the login form on failure.
    """
    if not keycloak.is_enabled():
        flash('Keycloak login is not configured on this instance.', 'error')
        return redirect(url_for('auth.login'))

    try:
        # Verifies state, exchanges the code, and validates the ID token.
        token = keycloak.get_client().authorize_access_token()
    except Exception as e:  # noqa: BLE001 - any failure here means "not signed in"
        logger.warning(f'Keycloak sign-in failed: {e}')
        flash('Keycloak sign-in failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    claims = token.get('userinfo') or {}
    username = (
        claims.get('preferred_username')
        or claims.get('email')
        or claims.get('sub')
        or 'keycloak user'
    )

    # No password: SPARQL endpoints are reached with the access token instead.
    session['user'] = {
        'username': username,
        'password': '',
        'is_authenticated': True,
        'auth_method': 'keycloak',
    }
    keycloak.store_tokens(token)

    # One login for all of it: the roles on the token decide which panels
    # appear, so there is no separate admin sign-in. Read once, at login.
    #
    # The two roles are independent — site administration and authorization
    # management are granted separately. Any elevation not backed by a role on
    # this token is cleared, so nothing is inherited from a previous session.
    if keycloak.has_admin_role(claims):
        session['is_admin'] = True
        session['admin_username'] = username
        logger.info(f'Admin session granted to {username} via Keycloak role')
    else:
        session.pop('is_admin', None)
        session.pop('admin_username', None)

    if keycloak.has_authz_admin_role(claims):
        session['is_authz_admin'] = True
        logger.info(
            f'Authorization-admin session granted to {username} via Keycloak role'
        )
    else:
        session.pop('is_authz_admin', None)

    session.modified = True

    flash(f'Welcome, {username}!', 'success')

    next_page = _safe_next(session.pop('keycloak_next', None))
    if next_page:
        return redirect(next_page)
    return redirect(url_for('main.index'))


@auth_bp.route('/logout', methods=['POST'])
def logout() -> str:
    """Handle user logout.

    Returns:
        Redirect to home page.
    """
    user = session.get('user', {})
    username = user.get('username', 'User')

    # Build the Keycloak logout URL before dropping the tokens — it needs the
    # ID token as a hint. Signing out locally without ending the Keycloak
    # session would let the next "Sign in with Keycloak" re-authenticate the
    # same user silently, which reads as a broken logout.
    keycloak_logout = None
    if user.get('auth_method') == 'keycloak' and keycloak.is_enabled():
        keycloak_logout = keycloak.logout_url(url_for('main.index', _external=True))

    # Clear user-related session data. Admin elevation goes with it: the two
    # are one session now, so signing out of the portal drops admin rights.
    session.pop('user', None)
    session.pop('endpoint_credentials', None)
    session.pop('query_result', None)
    session.pop('keycloak_next', None)
    session.pop('is_admin', None)
    session.pop('admin_username', None)
    session.pop('is_authz_admin', None)
    keycloak.clear_tokens()
    session.modified = True

    flash(f'Goodbye, {username}!', 'success')

    if keycloak_logout:
        return redirect(keycloak_logout)
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
        fdp_uri = existing.get('fdp_uri', '')
        cached_fdp = current_app.fdp_cache.get_fdp(fdp_uri) if fdp_uri else None
        fdp = {
            'uri': fdp_uri,
            'title': (cached_fdp or {}).get('title') or 'Configured endpoint',
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
