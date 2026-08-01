from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class AccountMove(models.Model):
    """Extension of account.move for EDI email notifications."""

    _inherit = "account.move"

    l10n_py_email_notification_sent = fields.Boolean(
        default=False,
        copy=False,
        help="Set to True after sending the EDI notification email",
    )

    l10n_py_email_notification_date = fields.Datetime(
        copy=False,
        help="When the notification email was sent",
    )

    l10n_py_email_recipient_ids = fields.Many2many(
        comodel_name="res.partner",
        compute="_compute_email_recipients",
        store=True,
        help="Partners to receive the EDI notification",
    )

    l10n_py_auto_send_email = fields.Boolean(
        default=True,
        help="If True, automatically send email when EDI status changes",
    )

    @api.depends("partner_id", "company_id")
    def _compute_email_recipients(self) -> None:
        """Compute email recipients based on partner and company.

        Recipients are:
        - Customer (partner) if they have an email
        - Internal contact if configured on company
        """
        for rec in self:
            recipients = self.env["res.partner"]

            # Customer email
            if rec.partner_id and rec.partner_id.email:
                recipients |= rec.partner_id

            # Company internal contact (field may not exist)
            notif_partner = getattr(
                rec.company_id, "l10n_py_edi_notification_partner_id", False
            )
            if notif_partner:
                recipients |= notif_partner

            rec.l10n_py_email_recipient_ids = recipients

    def _send_edi_notification_email(self) -> bool:
        """Send EDI notification email to recipients.

        Attaches the XML and KuDE PDF to the email.
        Called automatically when EDI status changes.

        Returns:
            True on success, False on failure.
        """
        self.ensure_one()

        if not self.l10n_py_auto_send_email:
            return False

        if not self.l10n_py_email_recipient_ids:
            self.message_post(
                body=self.env._(
                    "No email recipients configured. Cannot send EDI notification."
                ),
                message_type="comment",
            )
            return False

        # Determine template based on status
        if self.l10n_py_edi_status == "accepted":
            template = self.env.ref("l10n_py_edi_mail.mail_template_edi_accepted")
        elif self.l10n_py_edi_status == "rejected":
            template = self.env.ref("l10n_py_edi_mail.mail_template_edi_rejected")
        elif self.l10n_py_edi_status == "cancelled":
            template = self.env.ref("l10n_py_edi_mail.mail_template_edi_cancelled")
        else:
            return False

        # Prepare attachments
        attachment_ids = []

        # XML attachment
        if self.l10n_py_edi_xml:
            attachment = self.env["ir.attachment"].create(
                {
                    "name": f"EDI_{self.name}.xml",
                    "type": "binary",
                    "datas": self.l10n_py_edi_xml,
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
            attachment_ids.append(attachment.id)

        # KuDE PDF attachment
        if self.l10n_py_kude_pdf:
            attachment = self.env["ir.attachment"].create(
                {
                    "name": self.l10n_py_kude_filename or f"KUDE_{self.name}.pdf",
                    "type": "binary",
                    "datas": self.l10n_py_kude_pdf,
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
            attachment_ids.append(attachment.id)

        try:
            # Send email
            template.send_mail(
                self.id,
                force_send=True,
                email_values={
                    "attachment_ids": [(6, 0, attachment_ids)],
                    "recipient_ids": [
                        (4, p.id) for p in self.l10n_py_email_recipient_ids
                    ],
                },
            )

            # Mark as sent
            self.write(
                {
                    "l10n_py_email_notification_sent": True,
                    "l10n_py_email_notification_date": fields.Datetime.now(),
                }
            )

            self.message_post(
                body=self.env._(
                    "EDI notification email sent to %(recipients)s.",
                    recipients=", ".join(
                        self.l10n_py_email_recipient_ids.mapped("name")
                    ),
                ),
                message_type="comment",
            )

            return True

        except Exception as e:
            self.message_post(
                body=self.env._(
                    "Failed to send EDI notification email: %(error)s", error=str(e)
                ),
                message_type="warning",
            )
            return False

    def action_resend_notification(self) -> bool:
        """Manually resend the EDI notification email.

        Returns:
            True on success.
        """
        self.ensure_one()

        # Reset flag to allow resend
        self.write({"l10n_py_email_notification_sent": False})

        return self._send_edi_notification_email()

    @api.model
    def _cron_send_pending_notifications(self) -> None:
        """Send pending notification emails.

        Runs every 15 minutes to catch any notifications
        that failed in the initial attempt.
        """
        pending = self.search(
            [
                ("l10n_py_edi_status", "in", ["accepted", "rejected", "cancelled"]),
                ("l10n_py_auto_send_email", "=", True),
                ("l10n_py_email_notification_sent", "=", False),
            ]
        )

        for move in pending:
            try:
                move._send_edi_notification_email()
            except Exception as e:
                move.message_post(
                    body=self.env._(
                        "Failed to send pending notification: %(error)s",
                        error=str(e),
                    ),
                    message_type="warning",
                )
