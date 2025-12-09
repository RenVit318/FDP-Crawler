"""Email Composer for generating data access request emails."""

from typing import Dict, List

from app.models import DataRequest, DatasetReference, ComposedEmail


class EmailComposer:
    """Service for composing data access request emails."""

    def group_by_contact(
        self, request: DataRequest
    ) -> Dict[str, List[DatasetReference]]:
        """
        Group datasets by contact email for sending.

        Args:
            request: The data request containing datasets.

        Returns:
            Dict mapping email addresses to list of datasets.
        """
        groups: Dict[str, List[DatasetReference]] = {}

        for dataset in request.datasets:
            email = dataset.contact_email
            if email not in groups:
                groups[email] = []
            groups[email].append(dataset)

        return groups

    def compose_request_email(self, request: DataRequest) -> ComposedEmail:
        """
        Generate the email text for a data request.

        If datasets have different contacts, this generates a single email
        addressed to all contacts. Use compose_emails_by_contact() to generate
        separate emails per contact.

        Args:
            request: The completed data request.

        Returns:
            ComposedEmail with subject, body, and recipients.
        """
        # Collect all unique recipients
        recipients = list(set(ds.contact_email for ds in request.datasets))

        # Generate subject
        subject = self._generate_subject(request.datasets)

        # Generate body
        body = self._generate_body(request, request.datasets)

        return ComposedEmail(
            recipients=recipients,
            subject=subject,
            body=body,
        )

    def compose_emails_by_contact(
        self, request: DataRequest
    ) -> List[ComposedEmail]:
        """
        Generate separate emails for each contact.

        Args:
            request: The completed data request.

        Returns:
            List of ComposedEmail, one per unique contact.
        """
        groups = self.group_by_contact(request)
        emails = []

        for email, datasets in groups.items():
            subject = self._generate_subject(datasets)
            body = self._generate_body(request, datasets)

            composed = ComposedEmail(
                recipients=[email],
                subject=subject,
                body=body,
            )
            emails.append(composed)

        return emails

    def _generate_subject(self, datasets: List[DatasetReference]) -> str:
        """Generate email subject line."""
        if not datasets:
            return "Data Access Request"

        first_title = datasets[0].title
        if len(datasets) == 1:
            return f"Data Access Request - {first_title}"
        else:
            return f"Data Access Request - {first_title} + {len(datasets) - 1} more"

    def _generate_body(
        self, request: DataRequest, datasets: List[DatasetReference]
    ) -> str:
        """Generate email body following the template structure."""
        lines = []

        # Opening
        lines.append("Dear Data Steward,")
        lines.append("")
        lines.append(
            "I am writing to request access to data for analysis under a "
            "data visiting arrangement."
        )
        lines.append("")

        # Requester information
        lines.append("== REQUESTER INFORMATION ==")
        lines.append(f"Name: {request.requester_name}")
        lines.append(f"Email: {request.requester_email}")
        lines.append(f"Affiliation: {request.requester_affiliation}")
        if request.requester_orcid:
            lines.append(f"ORCID: {request.requester_orcid}")
        lines.append("")

        # Requested datasets
        lines.append("== REQUESTED DATASETS ==")
        for i, ds in enumerate(datasets, 1):
            lines.append(f"{i}. {ds.title}")
            lines.append(f"   URI: {ds.uri}")
            lines.append(f"   Source: {ds.fdp_title}")
            lines.append("")

        # Proposed query
        lines.append("== PROPOSED QUERY ==")
        lines.append(request.query)
        lines.append("")

        # Purpose
        lines.append("== PURPOSE / JUSTIFICATION ==")
        lines.append(request.purpose)
        lines.append("")

        # Output constraints (optional)
        if request.output_constraints:
            lines.append("== OUTPUT CONSTRAINTS ==")
            lines.append(request.output_constraints)
            lines.append("")

        # Timeline (optional)
        if request.timeline:
            lines.append("== TIMELINE ==")
            lines.append(request.timeline)
            lines.append("")

        # Closing
        lines.append(
            "I understand that the query will be executed locally on your systems "
            "and only verified/approved results will be returned. Please let me "
            "know if you require any additional information or documentation."
        )
        lines.append("")
        lines.append("Thank you for considering this request.")
        lines.append("")
        lines.append("Best regards,")
        lines.append(request.requester_name)
        lines.append(request.requester_affiliation)

        return "\n".join(lines)
