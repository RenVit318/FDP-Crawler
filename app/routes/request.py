"""Request composition routes."""

from flask import Blueprint, render_template, request, session, flash, redirect, url_for

from app.models import DataRequest, DatasetReference
from app.services import EmailComposer

request_bp = Blueprint('request', __name__, url_prefix='/request')


@request_bp.route('/')
def basket():
    """View current request basket."""
    basket_items = session.get('basket', [])

    # Group items by contact email for preview
    by_contact = {}
    for item in basket_items:
        contact = item.get('contact_point', {}) or {}
        email = contact.get('email', 'No contact email')

        if email not in by_contact:
            by_contact[email] = []
        by_contact[email].append(item)

    return render_template(
        'request/basket.html',
        basket=basket_items,
        by_contact=by_contact,
    )


@request_bp.route('/clear', methods=['POST'])
def clear():
    """Clear the request basket."""
    session['basket'] = []
    session.modified = True
    flash('Basket cleared.', 'success')
    return redirect(url_for('request.basket'))


@request_bp.route('/compose', methods=['GET', 'POST'])
def compose():
    """Compose a data access request."""
    basket_items = session.get('basket', [])

    if not basket_items:
        flash('Your basket is empty. Add datasets before composing a request.', 'warning')
        return redirect(url_for('datasets.browse'))

    # Check if all datasets have contact emails
    missing_contacts = []
    for item in basket_items:
        contact = item.get('contact_point', {}) or {}
        if not contact.get('email'):
            missing_contacts.append(item['title'])

    if request.method == 'POST':
        # Get form data
        requester_name = request.form.get('name', '').strip()
        requester_email = request.form.get('email', '').strip()
        requester_affiliation = request.form.get('affiliation', '').strip()
        requester_orcid = request.form.get('orcid', '').strip() or None
        query = request.form.get('query', '').strip()
        purpose = request.form.get('purpose', '').strip()
        output_constraints = request.form.get('output_constraints', '').strip() or None
        timeline = request.form.get('timeline', '').strip() or None

        # Validate required fields
        errors = []
        if not requester_name:
            errors.append('Name is required.')
        if not requester_email:
            errors.append('Email is required.')
        if not requester_affiliation:
            errors.append('Affiliation is required.')
        if not query:
            errors.append('Query/Analysis description is required.')
        if not purpose:
            errors.append('Purpose is required.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template(
                'request/compose.html',
                basket=basket_items,
                missing_contacts=missing_contacts,
                form_data=request.form,
            )

        # Create DatasetReference objects
        datasets = []
        for item in basket_items:
            contact = item.get('contact_point', {}) or {}
            contact_email = contact.get('email', 'unknown@example.com')

            datasets.append(DatasetReference(
                uri=item['uri'],
                title=item['title'],
                contact_email=contact_email,
                fdp_title=item['fdp_title'],
            ))

        # Create DataRequest
        data_request = DataRequest(
            requester_name=requester_name,
            requester_email=requester_email,
            requester_affiliation=requester_affiliation,
            requester_orcid=requester_orcid,
            datasets=datasets,
            query=query,
            purpose=purpose,
            output_constraints=output_constraints,
            timeline=timeline,
        )

        # Compose emails
        composer = EmailComposer()
        emails = composer.compose_emails_by_contact(data_request)

        # Store in session for preview
        session['composed_emails'] = [e.to_dict() for e in emails]
        session['data_request'] = data_request.to_dict()
        session.modified = True

        return redirect(url_for('request.preview'))

    return render_template(
        'request/compose.html',
        basket=basket_items,
        missing_contacts=missing_contacts,
        form_data={},
    )


@request_bp.route('/preview')
def preview():
    """Preview composed emails."""
    emails_data = session.get('composed_emails', [])
    request_data = session.get('data_request', {})

    if not emails_data:
        flash('No request to preview. Please compose a request first.', 'warning')
        return redirect(url_for('request.compose'))

    return render_template(
        'request/preview.html',
        emails=emails_data,
        request_data=request_data,
    )


@request_bp.route('/finish', methods=['POST'])
def finish():
    """Mark the request as complete and clear basket."""
    # Clear basket and composed emails
    session['basket'] = []
    session['composed_emails'] = []
    session['data_request'] = {}
    session.modified = True

    flash('Request process complete! You can copy the email content and send it to the contacts.', 'success')
    return redirect(url_for('main.index'))
