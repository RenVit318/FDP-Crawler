"""Keycloak / OIDC integration.

Entirely optional and inert until configured. The portal keeps its original
username/password login; when KEYCLOAK_SERVER_URL, KEYCLOAK_REALM and
KEYCLOAK_CLIENT_ID are all set (see app/config.py), a second "Sign in with
Keycloak" path appears alongside it and successful logins carry an OIDC access
token that is pushed to SPARQL endpoints as a bearer token.

The two login methods coexist deliberately: data providers migrate their
endpoints to token auth at their own pace, and endpoints still on HTTP Basic
keep working via per-endpoint credentials or the login password.

Single-realm assumption
-----------------------
One realm serves the whole data space, so a single access token is valid at
every SPARQL endpoint. That is why the query path resolves the token once per
federated run (see app/routes/sparql.py) rather than per endpoint.

If providers ever run their own realms, that assumption breaks: each endpoint
would then need an audience-specific token, obtained by token exchange against
its own realm. The change would be localised to get_valid_access_token() —
it would take the target endpoint as an argument — plus the loop in
sparql.py::query that currently reuses one token for all endpoints.

Session keys owned by this module:
    keycloak_tokens: {access_token, refresh_token, expires_at, id_token}

expires_at is an absolute POSIX timestamp, so a session restored from disk
(Flask-Session is filesystem-backed) still knows when its token went stale.
"""

import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from flask import Flask, current_app, session

try:
    from authlib.integrations.flask_client import OAuth
except ImportError:  # pragma: no cover - exercised only on installs without Authlib
    OAuth = None


logger = logging.getLogger(__name__)


SESSION_TOKEN_KEY = 'keycloak_tokens'

# Keycloak's OIDC endpoints follow a fixed layout under the realm. Used only as
# a fallback when the discovery document cannot be fetched.
_REALM_PATH = '{server}/realms/{realm}/protocol/openid-connect'


def init_app(app: Flask) -> None:
    """Register the Keycloak OAuth client on the app, if configured.

    Safe to call unconditionally: when Keycloak is not configured (or Authlib is
    not installed) this leaves ``app.keycloak_oauth`` as None and every other
    entry point in this module degrades to "no Keycloak".
    """
    app.keycloak_oauth = None

    if not _config_complete(app.config):
        return

    if OAuth is None:
        logger.warning(
            'Keycloak is configured but Authlib is not installed; '
            'Keycloak login is disabled. Install requirements.txt to enable it.'
        )
        return

    oauth = OAuth(app)
    oauth.register(
        name='keycloak',
        client_id=app.config['KEYCLOAK_CLIENT_ID'],
        client_secret=app.config.get('KEYCLOAK_CLIENT_SECRET') or None,
        server_metadata_url=(
            f"{app.config['KEYCLOAK_SERVER_URL']}/realms/"
            f"{app.config['KEYCLOAK_REALM']}/.well-known/openid-configuration"
        ),
        client_kwargs={
            'scope': app.config.get('KEYCLOAK_SCOPES', 'openid profile email'),
            'verify': app.config.get('KEYCLOAK_VERIFY_SSL', True),
        },
    )
    app.keycloak_oauth = oauth
    # Role names are logged so a deployment that forgot to override them for its
    # own dataspace (AHDS inheriting the HDS defaults, say) is visible at boot.
    logger.info(
        'Keycloak login enabled (realm=%s, client=%s, admin_role=%s, '
        'authz_admin_role=%s)',
        app.config['KEYCLOAK_REALM'],
        app.config['KEYCLOAK_CLIENT_ID'],
        app.config.get('KEYCLOAK_ADMIN_ROLE'),
        app.config.get('KEYCLOAK_AUTHZ_ADMIN_ROLE'),
    )


def _config_complete(config: Dict[str, Any]) -> bool:
    """Whether the three mandatory Keycloak settings are present."""
    return all(
        config.get(key)
        for key in ('KEYCLOAK_SERVER_URL', 'KEYCLOAK_REALM', 'KEYCLOAK_CLIENT_ID')
    )


def is_enabled() -> bool:
    """Whether Keycloak login is available on this instance."""
    return getattr(current_app, 'keycloak_oauth', None) is not None


def get_client():
    """Return the registered Authlib client, or None when Keycloak is disabled."""
    oauth = getattr(current_app, 'keycloak_oauth', None)
    return oauth.keycloak if oauth else None


def roles_from_claims(claims: Dict[str, Any]) -> set:
    """Extract the user's roles from OIDC claims.

    Reads both realm roles (``realm_access.roles``) and this client's roles
    (``resource_access.<client_id>.roles``), so either kind of Keycloak role
    grants access without the app needing to know which was used.

    Returns an empty set when no roles claim is present at all — which usually
    means the role mapper is missing on the Keycloak client rather than that
    the user genuinely has no roles, so that case is logged.
    """
    realm_roles = (claims.get('realm_access') or {}).get('roles') or []

    client_id = current_app.config.get('KEYCLOAK_CLIENT_ID', '')
    resource_access = claims.get('resource_access') or {}
    client_roles = (resource_access.get(client_id) or {}).get('roles') or []

    if 'realm_access' not in claims and 'resource_access' not in claims:
        logger.warning(
            'Keycloak ID token carries no roles claim. Add a role mapper to the '
            '%s client with "Add to ID token" enabled, or no one can be granted '
            'the admin role.',
            client_id or '<client>',
        )

    return set(realm_roles) | set(client_roles)


def has_admin_role(claims: Dict[str, Any]) -> bool:
    """Whether these claims grant the site-administration role."""
    return _has_role(claims, 'KEYCLOAK_ADMIN_ROLE')


def has_authz_admin_role(claims: Dict[str, Any]) -> bool:
    """Whether these claims grant the authorization-management role.

    Deliberately independent of has_admin_role: managing who may reach data at
    the AllegroGraph instances is a different, larger power than editing site
    content, so neither role implies the other.
    """
    return _has_role(claims, 'KEYCLOAK_AUTHZ_ADMIN_ROLE')


def _has_role(claims: Dict[str, Any], config_key: str) -> bool:
    """Whether the claims carry the role named by the given config key."""
    role = current_app.config.get(config_key)
    if not role:
        return False
    return role in roles_from_claims(claims)


def store_tokens(token: Dict[str, Any]) -> None:
    """Persist the tokens from an authorization-code or refresh exchange."""
    session[SESSION_TOKEN_KEY] = _normalize(token)
    session.modified = True


def clear_tokens() -> None:
    """Drop any stored tokens (logout, or an unrecoverable refresh failure)."""
    session.pop(SESSION_TOKEN_KEY, None)
    session.modified = True


def has_session_token() -> bool:
    """Whether this session holds a Keycloak access token.

    Cheap and side-effect free — it never refreshes. Use it for rendering
    decisions; use :func:`get_valid_access_token` when a token is about to be
    sent to an endpoint.
    """
    return bool((session.get(SESSION_TOKEN_KEY) or {}).get('access_token'))


def get_valid_access_token() -> Optional[str]:
    """Return a usable access token, refreshing it first if it is about to expire.

    Returns None when the session has no token, or when the token has expired
    and could not be renewed — callers then fall back to their other credential
    sources rather than sending a token the endpoint would reject.
    """
    tokens = session.get(SESSION_TOKEN_KEY) or {}
    access_token = tokens.get('access_token')
    if not access_token:
        return None

    expires_at = tokens.get('expires_at')
    leeway = current_app.config.get('KEYCLOAK_REFRESH_LEEWAY', 30)

    # No expiry information: nothing to act on, hand back what we have.
    if not expires_at:
        return access_token

    if time.time() < expires_at - leeway:
        return access_token

    refresh_token = tokens.get('refresh_token')
    if not refresh_token:
        logger.info('Keycloak access token expired and no refresh token is available')
        clear_tokens()
        return None

    refreshed = _refresh(refresh_token)
    if not refreshed:
        clear_tokens()
        return None

    store_tokens(refreshed)
    return refreshed.get('access_token')


def _refresh(refresh_token: str) -> Optional[Dict[str, Any]]:
    """Exchange a refresh token for a new access token.

    Returns the new token dict, or None if the refresh failed (expired session
    on the Keycloak side, revoked client, server unreachable).
    """
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': current_app.config['KEYCLOAK_CLIENT_ID'],
    }
    client_secret = current_app.config.get('KEYCLOAK_CLIENT_SECRET')
    if client_secret:
        data['client_secret'] = client_secret

    try:
        response = requests.post(
            _token_endpoint(),
            data=data,
            timeout=current_app.config.get('KEYCLOAK_TIMEOUT', 15),
            verify=current_app.config.get('KEYCLOAK_VERIFY_SSL', True),
        )
        if response.status_code != 200:
            logger.warning(
                'Keycloak token refresh failed (%s): %s',
                response.status_code,
                response.text[:200],
            )
            return None
        return _normalize(response.json())
    except (requests.RequestException, ValueError) as e:
        logger.warning(f'Keycloak token refresh failed: {e}')
        return None


def _normalize(token: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a token response to the fields we store, with an absolute expiry.

    Authlib already sets ``expires_at``; a raw refresh response only carries
    ``expires_in``, so derive it here and keep both paths storing the same shape.
    """
    expires_at = token.get('expires_at')
    if not expires_at and token.get('expires_in'):
        try:
            expires_at = time.time() + int(token['expires_in'])
        except (TypeError, ValueError):
            expires_at = None

    return {
        'access_token': token.get('access_token'),
        'refresh_token': token.get('refresh_token'),
        'id_token': token.get('id_token'),
        'expires_at': expires_at,
    }


def _server_metadata() -> Dict[str, Any]:
    """Load the OIDC discovery document (Authlib caches it after the first call)."""
    client = get_client()
    if client is None:
        return {}
    try:
        return client.load_server_metadata() or {}
    except Exception as e:  # noqa: BLE001 - discovery failure must not be fatal
        logger.warning(f'Could not load Keycloak server metadata: {e}')
        return {}


def _realm_url(suffix: str) -> str:
    """Build a conventional Keycloak endpoint URL for the configured realm."""
    base = _REALM_PATH.format(
        server=current_app.config['KEYCLOAK_SERVER_URL'],
        realm=current_app.config['KEYCLOAK_REALM'],
    )
    return f'{base}/{suffix}'


def _token_endpoint() -> str:
    """Token endpoint from discovery, falling back to the realm convention."""
    return _server_metadata().get('token_endpoint') or _realm_url('token')


def logout_url(post_logout_redirect_uri: str) -> Optional[str]:
    """Build the RP-initiated logout URL that also ends the Keycloak session.

    Without this, signing out of the portal leaves the Keycloak session intact
    and the next "Sign in with Keycloak" silently re-authenticates the same user,
    which reads as a broken logout. Returns None when Keycloak is disabled.
    """
    if not is_enabled():
        return None

    end_session = _server_metadata().get('end_session_endpoint') or _realm_url('logout')

    params = {
        'client_id': current_app.config['KEYCLOAK_CLIENT_ID'],
        'post_logout_redirect_uri': post_logout_redirect_uri,
    }
    id_token = (session.get(SESSION_TOKEN_KEY) or {}).get('id_token')
    if id_token:
        # Keycloak accepts post_logout_redirect_uri only alongside either
        # id_token_hint or client_id; sending the hint skips the confirm screen.
        params['id_token_hint'] = id_token

    return f'{end_session}?{urlencode(params)}'
