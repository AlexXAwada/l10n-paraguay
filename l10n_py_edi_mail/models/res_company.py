# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import fields, models

if TYPE_CHECKING:
    pass


class ResCompany(models.Model):
    """Extend company with EDI email notification settings."""

    _inherit = "res.company"

    l10n_py_edi_mail_enabled: bool = fields.Boolean(
        string="Enable EDI Email Notifications",
        default=True,
        help="Send automatic email notifications when EDI documents are "
        "accepted or rejected by SIFEN",
    )
    l10n_py_edi_mail_to_customer: bool = fields.Boolean(
        string="Notify Customer",
        default=True,
        help="Send notification to the customer (partner) when their "
        "document is accepted by SIFEN",
    )
    l10n_py_edi_mail_to_internal: bool = fields.Boolean(
        string="Notify Internal Users",
        default=True,
        help="Send notification to internal users when documents are "
        "rejected or require attention",
    )
    l10n_py_edi_mail_reject_alert: bool = fields.Boolean(
        string="Alert on Rejection",
        default=True,
        help="Send immediate alert to responsible users when a document "
        "is rejected by SIFEN",
    )
