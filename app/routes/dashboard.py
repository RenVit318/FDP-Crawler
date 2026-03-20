"""Public dashboard routes — aggregate statistics from SPARQL endpoints."""

from flask import Blueprint, render_template

from app.services import dashboard_service

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
def index():
    """Public dashboard showing pre-computed aggregate statistics."""
    data = dashboard_service.get_dashboard_data()
    return render_template('dashboard/index.html', data=data)
