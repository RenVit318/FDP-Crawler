"""Tests for the Email Composer."""

import pytest

from app.models import DataRequest, DatasetReference, ComposedEmail
from app.services.email_composer import EmailComposer


class TestEmailComposerGroupByContact:
    """Tests for EmailComposer.group_by_contact()."""

    def test_group_single_contact(self, sample_data_request):
        """Test grouping with single contact."""
        composer = EmailComposer()
        groups = composer.group_by_contact(sample_data_request)

        assert len(groups) == 1
        assert 'data-requests@example.org' in groups

    def test_group_multiple_contacts(self, multiple_dataset_references):
        """Test grouping with multiple different contacts."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=multiple_dataset_references,
            query='SELECT * FROM data',
            purpose='Research analysis',
        )

        composer = EmailComposer()
        groups = composer.group_by_contact(request)

        # Should have 2 groups (example.org has 2 datasets, other.org has 1)
        assert len(groups) == 2
        assert 'data-requests@example.org' in groups
        assert 'genomics@other.org' in groups
        assert len(groups['data-requests@example.org']) == 2
        assert len(groups['genomics@other.org']) == 1


class TestEmailComposerSubject:
    """Tests for email subject generation."""

    def test_subject_single_dataset(self, sample_dataset_reference):
        """Test subject line for single dataset."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=[sample_dataset_reference],
            query='SELECT * FROM data',
            purpose='Research analysis',
        )

        composer = EmailComposer()
        email = composer.compose_request_email(request)

        assert email.subject == 'Data Access Request - Biodiversity Survey Data 2023'

    def test_subject_multiple_datasets(self, multiple_dataset_references):
        """Test subject line for multiple datasets."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=multiple_dataset_references,
            query='SELECT * FROM data',
            purpose='Research analysis',
        )

        composer = EmailComposer()
        email = composer.compose_request_email(request)

        assert 'Biodiversity Survey Data 2023' in email.subject
        assert '+ 2 more' in email.subject


class TestEmailComposerBody:
    """Tests for email body generation."""

    def test_body_contains_requester_info(self, sample_data_request):
        """Test that body contains requester information."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert 'Dr. John Doe' in email.body
        assert 'j.doe@university.edu' in email.body
        assert 'University of Example' in email.body

    def test_body_contains_orcid_when_provided(self, sample_data_request):
        """Test that ORCID is included when provided."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert '0000-0002-1234-5678' in email.body

    def test_body_omits_orcid_when_not_provided(self, sample_dataset_reference):
        """Test that ORCID is omitted when not provided."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            requester_orcid=None,
            datasets=[sample_dataset_reference],
            query='SELECT * FROM data',
            purpose='Research analysis',
        )

        composer = EmailComposer()
        email = composer.compose_request_email(request)

        assert 'ORCID:' not in email.body

    def test_body_contains_dataset_info(self, sample_data_request):
        """Test that body contains dataset information."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert 'Biodiversity Survey Data 2023' in email.body
        assert 'https://example.org/fdp/dataset/biodiversity-2023' in email.body
        assert 'Example FAIR Data Point' in email.body

    def test_body_numbers_multiple_datasets(self, multiple_dataset_references):
        """Test that multiple datasets are numbered."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=multiple_dataset_references,
            query='SELECT * FROM data',
            purpose='Research analysis',
        )

        composer = EmailComposer()
        email = composer.compose_request_email(request)

        assert '1. Biodiversity Survey Data 2023' in email.body
        assert '2. Climate Observations Dataset' in email.body
        assert '3. Genomics Study Data' in email.body

    def test_body_contains_query(self, sample_data_request):
        """Test that body contains the proposed query."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert 'SELECT species, count FROM observations WHERE year = 2023' in email.body

    def test_body_contains_purpose(self, sample_data_request):
        """Test that body contains the purpose."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert 'species distribution patterns' in email.body

    def test_body_contains_output_constraints_when_provided(self, sample_data_request):
        """Test that output constraints are included when provided."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert 'OUTPUT CONSTRAINTS' in email.body
        assert 'Aggregated results only' in email.body

    def test_body_omits_output_constraints_when_not_provided(
        self, sample_dataset_reference
    ):
        """Test that output constraints are omitted when not provided."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=[sample_dataset_reference],
            query='SELECT * FROM data',
            purpose='Research analysis',
            output_constraints=None,
        )

        composer = EmailComposer()
        email = composer.compose_request_email(request)

        assert 'OUTPUT CONSTRAINTS' not in email.body

    def test_body_contains_timeline_when_provided(self, sample_data_request):
        """Test that timeline is included when provided."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert 'TIMELINE' in email.body
        assert '4 weeks' in email.body

    def test_body_omits_timeline_when_not_provided(self, sample_dataset_reference):
        """Test that timeline is omitted when not provided."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=[sample_dataset_reference],
            query='SELECT * FROM data',
            purpose='Research analysis',
            timeline=None,
        )

        composer = EmailComposer()
        email = composer.compose_request_email(request)

        assert 'TIMELINE' not in email.body

    def test_body_structure(self, sample_data_request):
        """Test that body follows the expected structure."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        # Check section headers exist in order
        sections = [
            'Dear Data Steward',
            '== REQUESTER INFORMATION ==',
            '== REQUESTED DATASETS ==',
            '== PROPOSED QUERY ==',
            '== PURPOSE / JUSTIFICATION ==',
            'Thank you for considering this request',
            'Best regards',
        ]

        last_pos = -1
        for section in sections:
            pos = email.body.find(section)
            assert pos > last_pos, f"Section '{section}' not found in expected position"
            last_pos = pos


class TestEmailComposerRecipients:
    """Tests for email recipient handling."""

    def test_single_recipient(self, sample_data_request):
        """Test email with single recipient."""
        composer = EmailComposer()
        email = composer.compose_request_email(sample_data_request)

        assert len(email.recipients) == 1
        assert 'data-requests@example.org' in email.recipients

    def test_multiple_unique_recipients(self, multiple_dataset_references):
        """Test email with multiple unique recipients."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=multiple_dataset_references,
            query='SELECT * FROM data',
            purpose='Research analysis',
        )

        composer = EmailComposer()
        email = composer.compose_request_email(request)

        assert len(email.recipients) == 2
        assert 'data-requests@example.org' in email.recipients
        assert 'genomics@other.org' in email.recipients


class TestEmailComposerByContact:
    """Tests for compose_emails_by_contact()."""

    def test_separate_emails_per_contact(self, multiple_dataset_references):
        """Test generating separate emails per contact."""
        request = DataRequest(
            requester_name='Dr. John Doe',
            requester_email='j.doe@university.edu',
            requester_affiliation='University of Example',
            datasets=multiple_dataset_references,
            query='SELECT * FROM data',
            purpose='Research analysis',
        )

        composer = EmailComposer()
        emails = composer.compose_emails_by_contact(request)

        assert len(emails) == 2

        # Find email for each contact
        example_email = next(
            e for e in emails if 'data-requests@example.org' in e.recipients
        )
        other_email = next(e for e in emails if 'genomics@other.org' in e.recipients)

        # Example email should have 2 datasets
        assert 'Biodiversity Survey Data 2023' in example_email.body
        assert 'Climate Observations Dataset' in example_email.body
        assert 'Genomics Study Data' not in example_email.body

        # Other email should have 1 dataset
        assert 'Genomics Study Data' in other_email.body
        assert 'Biodiversity Survey Data 2023' not in other_email.body

    def test_single_contact_returns_one_email(self, sample_data_request):
        """Test that single contact returns one email."""
        composer = EmailComposer()
        emails = composer.compose_emails_by_contact(sample_data_request)

        assert len(emails) == 1
        assert emails[0].recipients == ['data-requests@example.org']


class TestComposedEmailToDict:
    """Tests for ComposedEmail.to_dict()."""

    def test_to_dict(self):
        """Test ComposedEmail.to_dict() method."""
        email = ComposedEmail(
            recipients=['test@example.org'],
            subject='Test Subject',
            body='Test body content',
        )

        d = email.to_dict()

        assert d['recipients'] == ['test@example.org']
        assert d['subject'] == 'Test Subject'
        assert d['body'] == 'Test body content'
