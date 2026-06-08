from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class EDISummary(models.Model):
    """EDI summary statistics for daily reporting."""

    _name = "l10n_py.edi.summary"
    _description = "EDI Daily Summary"
    _order = "date desc"

    date = fields.Date(
        string="Date",
        required=True,
        index=True,
        default=fields.Date.context_today,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # Document counts
    total_documents = fields.Integer(string="Total Documents")
    sent_today = fields.Integer(string="Sent Today")
    accepted_today = fields.Integer(string="Accepted Today")
    rejected_today = fields.Integer(string="Rejected Today")
    pending_response = fields.Integer(string="Pending Response")

    # Type breakdown
    fe_count = fields.Integer(string="FE Count")
    afe_count = fields.Integer(string="AFE Count")
    nce_count = fields.Integer(string="NCE Count")
    nde_count = fields.Integer(string="NDE Count")
    nre_count = fields.Integer(string="NRE Count")

    # Performance
    avg_response_time = fields.Float(
        string="Avg Response Time (min)",
        digits=(5, 2),
    )

    success_rate = fields.Float(
        string="Success Rate (%)",
        digits=(5, 2),
    )

    # Top errors
    top_error_1 = fields.Char(string="Top Error 1")
    top_error_1_count = fields.Integer(string="Top Error 1 Count")
    top_error_2 = fields.Char(string="Top Error 2")
    top_error_2_count = fields.Integer(string="Top Error 2 Count")
    top_error_3 = fields.Char(string="Top Error 3")
    top_error_3_count = fields.Integer(string="Top Error 3 Count")

    # Email sent
    email_sent = fields.Boolean(string="Email Sent", default=False)
    email_sent_date = fields.Datetime(string="Email Sent Date")

    @api.model
    def _compute_daily_summary(self, date=None) -> dict[str, Any]:
        """Compute daily summary statistics.

        Args:
            date: Date to compute summary for. Defaults to today.

        Returns:
            Dictionary with summary statistics.
        """
        if date is None:
            date = fields.Date.context_today(self)

        company = self.env.company

        # Base domain
        domain = [
            ("company_id", "=", company.id),
            ("invoice_date", "=", date),
        ]

        all_docs = self.env["account.move"].search(domain)
        total = len(all_docs)

        # Status counts
        accepted = all_docs.filtered(lambda d: d.l10n_py_edi_status == "accepted")
        rejected = all_docs.filtered(lambda d: d.l10n_py_edi_status == "rejected")
        pending = all_docs.filtered(
            lambda d: d.l10n_py_edi_status in ("sent", "pending")
        )

        # Type counts (using document type code)
        fe = all_docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "1")
        afe = all_docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "4")
        nce = all_docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "5")
        nde = all_docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "6")
        nre = all_docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "7")

        # Success rate
        completed = len(accepted) + len(rejected)
        success_rate = (len(accepted) / completed * 100) if completed > 0 else 0

        # Top errors (from rejected documents)
        reject_logs = self.env["l10n_py.edi.log"].search(
            [
                ("operation_type", "=", "send"),
                ("success", "=", False),
                ("create_date", ">=", fields.Datetime.start_of(date, "day")),
                ("create_date", "<=", fields.Datetime.end_of(date, "day")),
            ]
        )

        error_counts = {}
        for log in reject_logs:
            code = log.error_code or "UNKNOWN"
            error_counts[code] = error_counts.get(code, 0) + 1

        sorted_errors = sorted(error_counts.items(), key=lambda x: -x[1])[:3]
        top_errors = [(f"Error {e[0]}", e[1]) for e in sorted_errors]

        return {
            "date": date,
            "company_id": company.id,
            "total_documents": total,
            "sent_today": len(
                all_docs.filtered(
                    lambda d: d.l10n_py_edi_status in ("sent", "pending", "accepted")
                )
            ),
            "accepted_today": len(accepted),
            "rejected_today": len(rejected),
            "pending_response": len(pending),
            "fe_count": len(fe),
            "afe_count": len(afe),
            "nce_count": len(nce),
            "nde_count": len(nde),
            "nre_count": len(nre),
            "success_rate": success_rate,
            "avg_response_time": 0.0,
            "top_error_1": top_errors[0][0] if len(top_errors) > 0 else "",
            "top_error_1_count": top_errors[0][1] if len(top_errors) > 0 else 0,
            "top_error_2": top_errors[1][0] if len(top_errors) > 1 else "",
            "top_error_2_count": top_errors[1][1] if len(top_errors) > 1 else 0,
            "top_error_3": top_errors[2][0] if len(top_errors) > 2 else "",
            "top_error_3_count": top_errors[2][1] if len(top_errors) > 2 else 0,
        }

    @api.model
    def _cron_generate_daily_summary(self) -> None:
        """Generate and store daily summary. Run at end of day."""
        date = fields.Date.context_today(self)
        company = self.env.company

        # Check if already exists
        existing = self.search(
            [
                ("date", "=", date),
                ("company_id", "=", company.id),
            ]
        )

        if existing:
            # Update existing
            data = self._compute_daily_summary(date)
            existing.write(data)
        else:
            # Create new
            data = self._compute_daily_summary(date)
            self.create(data)

    @api.model
    def _cron_send_daily_summary_email(self) -> None:
        """Send daily summary email. Run once per day."""
        date = fields.Date.context_today(self)
        company = self.env.company

        summary = self.search(
            [
                ("date", "=", date),
                ("company_id", "=", company.id),
            ]
        )

        if not summary:
            # Generate if not exists
            self._cron_generate_daily_summary()
            summary = self.search(
                [
                    ("date", "=", date),
                    ("company_id", "=", company.id),
                ]
            )

        if summary and not summary.email_sent:
            try:
                template = self.env.ref(
                    "l10n_py_edi_summary.mail_template_daily_summary"
                )
                template.send_mail(summary.id, force_send=True)
                summary.write(
                    {
                        "email_sent": True,
                        "email_sent_date": fields.Datetime.now(),
                    }
                )
            except Exception as e:
                _logger.warning("Failed to send daily summary email: %s", str(e))

    def action_view_documents(self) -> dict:
        """View documents for this summary date."""
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Documents for %(date)s", date=self.date),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("invoice_date", "=", self.date),
                ("company_id", "=", self.company_id.id),
            ],
        }
