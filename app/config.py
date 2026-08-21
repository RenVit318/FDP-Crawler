"""Configuration management for the fairdataspace application."""

import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Application configuration loaded from environment variables."""

    SECRET_KEY: str = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    FDP_TIMEOUT: int = int(os.environ.get('FDP_TIMEOUT', 30))
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
    FDP_VERIFY_SSL: bool = os.environ.get('FDP_VERIFY_SSL', 'false').lower() != 'false'

    # DEFAULT_FDPS is supplied by the selected dataspace (see dataspaces/<name>/config.py).

    # SPARQL settings
    SPARQL_TIMEOUT: int = int(os.environ.get('SPARQL_TIMEOUT', 60))

    # Cache settings
    CACHE_REFRESH_INTERVAL: int = int(os.environ.get('CACHE_REFRESH_INTERVAL', 86400))

    # Dashboard settings
    DASHBOARD_SPARQL_USERNAME: str = os.environ.get('DASHBOARD_SPARQL_USERNAME', '')
    DASHBOARD_SPARQL_PASSWORD: str = os.environ.get('DASHBOARD_SPARQL_PASSWORD', '')
    DASHBOARD_REFRESH_INTERVAL: int = int(os.environ.get('DASHBOARD_REFRESH_INTERVAL', 86400))
    DASHBOARD_SPARQL_TIMEOUT: int = int(os.environ.get('DASHBOARD_SPARQL_TIMEOUT', 120))
    DASHBOARD_REPO_NAME: str = os.environ.get('DASHBOARD_REPO_NAME', 'Dashboard')

    # Auto-login settings
    #
    # When AUTO_LOGIN_USERNAME is set, every visitor to this instance is signed in
    # as that user automatically and the login/logout controls are hidden. Intended
    # for a dedicated deployment (e.g. the sandbox instance) where the audience
    # should never type credentials; the password stays in the server environment.
    # Leave unset on public instances — they keep the normal login flow.
    AUTO_LOGIN_USERNAME: str = os.environ.get('AUTO_LOGIN_USERNAME', '')
    AUTO_LOGIN_PASSWORD: str = os.environ.get('AUTO_LOGIN_PASSWORD', '')

    # Keycloak / OIDC settings
    #
    # Unset by default — the Keycloak server is not hosted yet, and with these
    # blank the app behaves exactly as before. Setting SERVER_URL, REALM and
    # CLIENT_ID together adds a "Sign in with Keycloak" option next to the
    # username/password form; users who take it get an access token that is sent
    # to SPARQL endpoints as `Authorization: Bearer ...` instead of HTTP Basic.
    # Per-endpoint credentials configured under /auth/credentials still win, so
    # providers that have not moved to token auth keep working.
    #
    # The redirect URI to register on the Keycloak client is
    # <site>/auth/keycloak/callback, and the post-logout redirect is <site>/.
    KEYCLOAK_SERVER_URL: str = os.environ.get('KEYCLOAK_SERVER_URL', '').rstrip('/')
    KEYCLOAK_REALM: str = os.environ.get('KEYCLOAK_REALM', '')
    KEYCLOAK_CLIENT_ID: str = os.environ.get('KEYCLOAK_CLIENT_ID', '')
    KEYCLOAK_CLIENT_SECRET: str = os.environ.get('KEYCLOAK_CLIENT_SECRET', '')
    KEYCLOAK_SCOPES: str = os.environ.get('KEYCLOAK_SCOPES', 'openid profile email')
    KEYCLOAK_TIMEOUT: int = int(os.environ.get('KEYCLOAK_TIMEOUT', 15))
    # Refresh this many seconds before the access token actually expires, so a
    # query that takes a while to start does not go out with a stale token.
    KEYCLOAK_REFRESH_LEEWAY: int = int(os.environ.get('KEYCLOAK_REFRESH_LEEWAY', 30))
    KEYCLOAK_VERIFY_SSL: bool = os.environ.get('KEYCLOAK_VERIFY_SSL', 'true').lower() != 'false'

    # Treat every request as https, regardless of what the reverse proxy
    # forwards. The public deployment is https-only, so generated external URLs
    # (above all the Keycloak redirect URI, which Keycloak matches literally
    # against the client registration) must never come out as http://.
    #
    # Enabled in docker-compose.yml; left off for local development over http.
    FORCE_HTTPS: bool = os.environ.get('FORCE_HTTPS', 'false').lower() == 'true'

    # Flask session settings
    SESSION_TYPE: str = 'filesystem'
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
