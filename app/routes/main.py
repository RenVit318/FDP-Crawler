"""Main routes for the fairdataspace application."""

from flask import Blueprint, render_template, session

from app.services.admin_service import get_page_content

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Render the landing page."""
    fdp_count = len(session.get('fdps', {}))
    basket_count = len(session.get('basket', []))
    datasets_cache = session.get('datasets_cache', [])
    # None means "not fetched yet this session" so the template shows an em dash.
    distribution_count = (
        sum(ds.get('distribution_count', 0) for ds in datasets_cache)
        if datasets_cache else None
    )
    content = get_page_content('home')

    return render_template(
        'index.html',
        fdp_count=fdp_count,
        basket_count=basket_count,
        distribution_count=distribution_count,
        page=content,
    )


@main_bp.route('/about')
def about():
    """Render the about page."""
    content = get_page_content('about')
    return render_template('about.html', page=content)
