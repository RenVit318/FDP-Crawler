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
    CACHE_REFRESH_INTERVAL: int = int(os.environ.get('CACHE_REFRESH_INTERVAL', 300))

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

    # Flask session settings
    SESSION_TYPE: str = 'filesystem'
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
