"""Dataset browsing routes."""

import hashlib
from flask import Blueprint, render_template, request, session, flash, redirect, url_for

from app.services import FDPClient, DatasetService, FDPError
from app.config import Config
from app.models import Dataset, ContactPoint

datasets_bp = Blueprint('datasets', __name__, url_prefix='/datasets')

DATASETS_PER_PAGE = 10


def get_uri_hash(uri: str) -> str:
    """Generate MD5 hash of URI for use as identifier."""
    return hashlib.md5(uri.encode()).hexdigest()


def get_cached_datasets() -> list:
    """Get datasets from cache, fetching if needed."""
    return session.get('datasets_cache', [])


def dataset_from_dict(data: dict) -> Dataset:
    """Reconstruct Dataset from dictionary."""
    contact_data = data.get('contact_point')
    contact_point = None
    if contact_data:
        contact_point = ContactPoint(
            name=contact_data.get('name'),
            email=contact_data.get('email'),
            url=contact_data.get('url'),
        )

    return Dataset(
        uri=data['uri'],
        title=data['title'],
        catalog_uri=data['catalog_uri'],
        fdp_uri=data['fdp_uri'],
        fdp_title=data['fdp_title'],
        description=data.get('description'),
        publisher=data.get('publisher'),
        creator=data.get('creator'),
        issued=None,  # Skip datetime parsing for simplicity
        modified=None,
        themes=data.get('themes', []),
        theme_labels=data.get('theme_labels', []),
        keywords=data.get('keywords', []),
        contact_point=contact_point,
        landing_page=data.get('landing_page'),
        distributions=data.get('distributions', []),
    )


def fetch_all_datasets() -> list:
    """Fetch all datasets from configured FDPs."""
    fdps = session.get('fdps', {})

    if not fdps:
        return []

    client = FDPClient(timeout=Config.FDP_TIMEOUT)
    service = DatasetService(client)

    # Get list of FDP URIs
    fdp_uris = [fdp_data['uri'] for fdp_data in fdps.values()]

    # Fetch all datasets
    datasets = service.get_all_datasets(fdp_uris)

    # Cache in session
    datasets_dicts = [ds.to_dict() for ds in datasets]
    session['datasets_cache'] = datasets_dicts
    session.modified = True

    return datasets_dicts


@datasets_bp.route('/')
def browse():
    """Browse all datasets with filtering and pagination."""
    # Get filter parameters
    query = request.args.get('q', '').strip()
    theme_filter = request.args.get('theme', '').strip()
    sort_by = request.args.get('sort', 'title')
    page = request.args.get('page', 1, type=int)

    # Get datasets from cache
    datasets_dicts = get_cached_datasets()

    if not datasets_dicts:
        # Try to fetch if we have FDPs configured
        fdps = session.get('fdps', {})
        if fdps:
            datasets_dicts = fetch_all_datasets()

    # Convert to Dataset objects for filtering
    datasets = [dataset_from_dict(d) for d in datasets_dicts]

    # Initialize service for filtering (no client needed for filtering)
    client = FDPClient(timeout=Config.FDP_TIMEOUT)
    service = DatasetService(client)

    # Get available themes before filtering
    themes = service.get_available_themes(datasets)

    # Apply search filter
    if query:
        datasets = service.search(datasets, query)

    # Apply theme filter
    if theme_filter:
        datasets = service.filter_by_theme(datasets, theme_filter)

    # Sort datasets
    if sort_by == 'title':
        datasets.sort(key=lambda d: (d.title or '').lower())
    elif sort_by == 'modified':
        datasets.sort(key=lambda d: d.modified or '', reverse=True)
    elif sort_by == 'fdp':
        datasets.sort(key=lambda d: (d.fdp_title or '').lower())

    # Pagination
    total_datasets = len(datasets)
    total_pages = (total_datasets + DATASETS_PER_PAGE - 1) // DATASETS_PER_PAGE
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1

    start_idx = (page - 1) * DATASETS_PER_PAGE
    end_idx = start_idx + DATASETS_PER_PAGE
    paginated_datasets = datasets[start_idx:end_idx]

    # Get basket items for highlighting
    basket = session.get('basket', [])
    basket_uris = {item['uri'] for item in basket}

    return render_template(
        'datasets/browse.html',
        datasets=paginated_datasets,
        themes=themes,
        query=query,
        theme_filter=theme_filter,
        sort_by=sort_by,
        page=page,
        total_pages=total_pages,
        total_datasets=total_datasets,
        basket_uris=basket_uris,
        get_uri_hash=get_uri_hash,
    )


@datasets_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh the dataset cache by fetching from all FDPs."""
    fdps = session.get('fdps', {})

    if not fdps:
        flash('No FDPs configured. Add an FDP first.', 'warning')
        return redirect(url_for('datasets.browse'))

    try:
        datasets_dicts = fetch_all_datasets()
        flash(f'Successfully refreshed {len(datasets_dicts)} dataset(s).', 'success')
    except Exception as e:
        flash('Error refreshing datasets. Please try again.', 'error')

    return redirect(url_for('datasets.browse'))


@datasets_bp.route('/<uri_hash>')
def detail(uri_hash: str):
    """Show dataset detail view."""
    # Find dataset in cache
    datasets_dicts = get_cached_datasets()

    dataset_dict = None
    for d in datasets_dicts:
        if get_uri_hash(d['uri']) == uri_hash:
            dataset_dict = d
            break

    if not dataset_dict:
        flash('Dataset not found.', 'error')
        return redirect(url_for('datasets.browse'))

    dataset = dataset_from_dict(dataset_dict)

    # Check if in basket
    basket = session.get('basket', [])
    in_basket = any(item['uri'] == dataset.uri for item in basket)

    return render_template(
        'datasets/detail.html',
        dataset=dataset,
        uri_hash=uri_hash,
        in_basket=in_basket,
    )


@datasets_bp.route('/<uri_hash>/add-to-basket', methods=['POST'])
def add_to_basket(uri_hash: str):
    """Add a dataset to the request basket."""
    # Find dataset in cache
    datasets_dicts = get_cached_datasets()

    dataset_dict = None
    for d in datasets_dicts:
        if get_uri_hash(d['uri']) == uri_hash:
            dataset_dict = d
            break

    if not dataset_dict:
        flash('Dataset not found.', 'error')
        return redirect(url_for('datasets.browse'))

    # Check if already in basket
    basket = session.get('basket', [])
    if any(item['uri'] == dataset_dict['uri'] for item in basket):
        flash('Dataset is already in your basket.', 'info')
    else:
        # Add to basket
        basket.append({
            'uri': dataset_dict['uri'],
            'uri_hash': uri_hash,
            'title': dataset_dict['title'],
            'fdp_title': dataset_dict['fdp_title'],
            'contact_point': dataset_dict.get('contact_point'),
        })
        session['basket'] = basket
        session.modified = True
        flash(f'Added "{dataset_dict["title"]}" to your basket.', 'success')

    # Redirect back to the referring page
    next_url = request.form.get('next') or request.referrer or url_for('datasets.browse')
    return redirect(next_url)


@datasets_bp.route('/<uri_hash>/remove-from-basket', methods=['POST'])
def remove_from_basket(uri_hash: str):
    """Remove a dataset from the request basket."""
    basket = session.get('basket', [])

    # Find and remove the dataset
    new_basket = [item for item in basket if item.get('uri_hash') != uri_hash]

    if len(new_basket) == len(basket):
        flash('Dataset not found in basket.', 'error')
    else:
        session['basket'] = new_basket
        session.modified = True
        flash('Removed dataset from basket.', 'success')

    # Redirect back to the referring page
    next_url = request.form.get('next') or request.referrer or url_for('datasets.browse')
    return redirect(next_url)
