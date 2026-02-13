"""Configuration management for the Data Visiting PoC application."""

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
    FDP_VERIFY_SSL: bool = os.environ.get('FDP_VERIFY_SSL', 'true').lower() != 'false'

    # SPARQL settings
    SPARQL_TIMEOUT: int = int(os.environ.get('SPARQL_TIMEOUT', 60))

    # Flask session settings
    SESSION_TYPE: str = 'filesystem'
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
