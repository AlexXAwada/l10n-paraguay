from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class ResCompany(models.Model):
    """Extension of res.company for certificate expiry notifications."""

    _inherit = "res.company"

    l10n_py_cert_expiry_warning_days = fields.Integer(
        string="Warning Days",
        default=30,
        help="Days before expiry to send warning notifications",
    )

    l10n_py_cert_notification_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Certificate Notification Contact",
        help="Partner who receives certificate expiry notifications",
    )

    @api.constrains("l10n_py_certificate_expiry")
    def _check_certificate_expiry(self) -> None:
        """Warn if certificate is already expired."""
        today = date.today()
        for company in self:
            if company.l10n_py_certificate_expiry:
                expiry_date = fields.Date.to_date(company.l10n_py_certificate_expiry)
                if expiry_date < today:
                    try:
                        company.sudo().message_post(
                            body=company.env._(
                                "SIFEN certificate has EXPIRED on %(date)s. "
                                "Please renew immediately to continue sending.",
                                date=expiry_date,
                            ),
                            message_type="warning",
                        )
                    except Exception as e:
                        _logger.debug(
                            "Cannot post message during constraint: %s", str(e)
                        )

    @api.model
    def _cron_check_certificate_expiry(self) -> None:
        """Check certificate expiry for all companies and send notifications."""
        today = date.today()
        companies = self.search([], limit=100)

        for company in companies:
            if not company.l10n_py_certificate_expiry:
                continue

            expiry_date = fields.Date.to_date(company.l10n_py_certificate_expiry)
            days_to_expiry = (expiry_date - today).days

            warning_days = company.l10n_py_cert_expiry_warning_days or 30

            # Send notification if within warning period
            if 0 <= days_to_expiry <= warning_days:
                last_notification = self.env["mail.message"].search(
                    [
                        ("model", "=", "res.company"),
                        ("res_id", "=", company.id),
                        ("body", "ilike", "certificate"),
                        ("body", "ilike", "expiry"),
                        (
                            "create_date",
                            ">=",
                            fields.Datetime.start_of(fields.Datetime.now(), "day"),
                        ),
                    ],
                    limit=1,
                )

                if not last_notification:
                    try:
                        template = self.env.ref(
                            "l10n_py_cert_expiry.mail_template_cert_expiry_warning"
                        )
                        recipient = (
                            company.l10n_py_cert_notification_partner_id
                            or company.partner_id
                        )
                        if recipient and recipient.email:
                            template.send_mail(
                                company.id,
                                force_send=True,
                                email_values={
                                    "recipient_ids": [(4, recipient.id)],
                                },
                            )
                    except Exception as e:
                        _logger.debug(
                            "Cannot send cert expiry notification: %s", str(e)
                        )

            # Also notify if expired today
            elif days_to_expiry < 0:
                last_expired = self.env["mail.message"].search(
                    [
                        ("model", "=", "res.company"),
                        ("res_id", "=", company.id),
                        ("body", "ilike", "EXPIRED"),
                        (
                            "create_date",
                            ">=",
                            fields.Datetime.start_of(fields.Datetime.now(), "day"),
                        ),
                    ],
                    limit=1,
                )

                if not last_expired:
                    try:
                        company.sudo().message_post(
                            body=company.env._(
                                "SIFEN certificate has EXPIRED on %(date)s. "
                                "EDI cannot be sent until certificate is renewed.",
                                date=expiry_date,
                            ),
                            message_type="warning",
                        )
                    except Exception as e:
                        _logger.debug("Cannot post expired cert message: %s", str(e))
