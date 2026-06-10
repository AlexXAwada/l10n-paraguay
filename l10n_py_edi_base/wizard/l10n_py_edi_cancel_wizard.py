# l10n_py_edi_base/wizard/l10n_py_edi_cancel_wizard.py

from odoo import api, fields, models
from odoo.exceptions import UserError

# Cancellation limits by document type (in hours)
CANCEL_LIMITS = {
    "1": 48,  # FE: 48 horas
    "4": 48,  # AFE: 48 horas
    "5": 168,  # NCE: 168 hours (7 days)
    "6": 168,  # NDE: 168 horas
    "7": 168,  # NRE: 168 horas
}


class EDICancelWizard(models.TransientModel):
    _name = "l10n_py.edi.cancel.wizard"
    _description = "Wizard to cancel EDI document"

    invoice_id = fields.Many2one("account.move", string="Invoice", required=True)
    motive = fields.Text(string="Cancellation Reason", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_id"):
            res["invoice_id"] = self.env.context["active_id"]
        return res

    def action_cancel(self):
        """Cancel EDI document con deadline verification."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(self.env._("No invoice selected"))

        if not self.invoice_id.l10n_py_cdc:
            raise UserError(self.env._("Invoice has no CDC, cannot cancel"))

        # Verify cancellation deadline
        self._check_cancel_deadline()

        self.invoice_id.action_cancel_edi(motive=self.motive)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Cancellation Successful"),
                "message": self.env._("The document has been cancelled"),
                "type": "success",
                "sticky": False,
            },
        }

    def _check_cancel_deadline(self):
        """Verify si el cancellation deadline has not expired."""
        invoice = self.invoice_id
        doc_type_code = (
            invoice.l10n_latam_document_type_id.code
            if invoice.l10n_latam_document_type_id
            else ""
        )

        limit_hours = CANCEL_LIMITS.get(doc_type_code, 48)

        # Compute hours since acceptance
        accepted_dt = invoice.l10n_py_edi_accepted_date or invoice.write_date
        if invoice.l10n_py_edi_status == "accepted":
            if not accepted_dt:
                raise UserError(
                    self.env._(
                        "Cannot cancel: EDI acceptance date is not "
                        "registered. Contact the administrator."
                    )
                )
            now = fields.Datetime.now()
            delta = now - accepted_dt
            hours_since = delta.total_seconds() / 3600

            if hours_since > limit_hours:
                raise UserError(
                    self.env._(
                        "The cancellation deadline has expired. "
                        "Type %(doc_type)s allows cancellation until "
                        "%(limit)s hours after acceptance "
                        "(%(elapsed).0f hours have elapsed).",
                        doc_type=invoice.l10n_latam_document_type_id.name
                        or doc_type_code,
                        limit=limit_hours,
                        elapsed=hours_since,
                    )
                )
