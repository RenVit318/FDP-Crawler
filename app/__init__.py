"""Flask application factory for the Data Visiting PoC."""

import logging
from typing import Optional, Dict, Any

from flask import Flask

from app.config import Config


def create_app(config_override: Optional[Dict[str, Any]] = None) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_override: Optional dictionary of configuration overrides.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Apply any overrides
    if config_override:
        app.config.update(config_override)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO')),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.fdp import fdp_bp
    from app.routes.datasets import datasets_bp
    from app.routes.request import request_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(fdp_bp)
    app.register_blueprint(datasets_bp)
    app.register_blueprint(request_bp)

    # Initialize session defaults
    @app.before_request
    def init_session():
        from flask import session
        if 'fdps' not in session:
            session['fdps'] = {}
        if 'basket' not in session:
            session['basket'] = []
        if 'datasets_cache' not in session:
            session['datasets_cache'] = []

    return app
