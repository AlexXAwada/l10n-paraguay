# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from odoo import api, fields, models

if TYPE_CHECKING:
    from odoo.addons.account.models import AccountMove
    from odoo.addons.base.models.res_company import Company


class BatchSendWizard(models.TransientModel):
    """Wizard to create a batch job from selected invoices."""

    _name = "l10n_py.batch.send.wizard"
    _description = "Batch Send Wizard"

    move_ids: AccountMove = fields.Many2many(
        "account.move",
        required=True,
        help="Invoices to include in the batch",
    )
    batch_type: str = fields.Selection(
        [
            ("send", "Send Documents"),
            ("status_check", "Check Status"),
            ("cancel", "Cancel Documents"),
        ],
        required=True,
        default="send",
    )
    batch_size: int = fields.Integer(
        default=50,
        help="Maximum documents per batch call (max 50 for SIFEN)",
    )
    job_name: str = fields.Char(
        compute="_compute_job_name",
        store=True,
        readonly=False,
    )
    company_id: Company = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    @api.depends("batch_type")
    def _compute_job_name(self) -> None:
        """Compute default job name from batch type."""
        for rec in self:
            type_labels = dict(rec._fields["batch_type"].selection)
            label = type_labels.get(rec.batch_type, rec.batch_type or "Batch")
            rec.job_name = (
                f"{label} - {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

    def action_create_batch(self) -> dict[str, Any]:
        """Create batch job and lines, return to job.

        Returns:
            Action to open the created batch job.
        """
        self.ensure_one()
        if not self.move_ids:
            raise models.UserError(self.env._("Please select at least one invoice"))

        # Validate batch size
        if self.batch_size <= 0 or self.batch_size > 50:
            raise models.UserError(self.env._("Batch size must be between 1 and 50"))

        # Create batch job
        job = self.env["l10n_py.batch.job"].create(
            {
                "name": self.job_name,
                "company_id": self.company_id.id,
                "batch_type": self.batch_type,
                "batch_size": self.batch_size,
                "move_ids": [(6, 0, self.move_ids.ids)],
            }
        )

        # Create lines and queue
        job.action_queue()

        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n_py.batch.job",
            "res_id": job.id,
            "view_mode": "form",
            "target": "current",
        }
