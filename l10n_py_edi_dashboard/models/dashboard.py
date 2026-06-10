# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import api, fields, models

if TYPE_CHECKING:
    from odoo.addons.base.models.res_company import Company


class EDIDashboard(models.Model):
    """Dashboard KPIs for EDI operations.

    Provides computed statistics about document statuses,
    send success rates, and pending actions.
    """

    _name = "l10n_py.edi.dashboard"
    _description = "EDI Dashboard"
    _auto_refresh = True

    # KPI fields (all computed)
    total_documents: int = fields.Integer(
        compute="_compute_totals",
        string="Total Documents",
    )
    pending_send: int = fields.Integer(
        compute="_compute_totals",
        string="Pending Send",
    )
    sent_pending_response: int = fields.Integer(
        compute="_compute_totals",
        string="Awaiting Response",
    )
    accepted_today: int = fields.Integer(
        compute="_compute_totals",
        string="Accepted Today",
    )
    rejected_today: int = fields.Integer(
        compute="_compute_totals",
        string="Rejected Today",
    )
    accepted_this_week: int = fields.Integer(
        compute="_compute_totals",
        string="This Week",
    )
    accepted_this_month: int = fields.Integer(
        compute="_compute_totals",
        string="This Month",
    )
    avg_response_time: float = fields.Float(
        compute="_compute_totals",
        string="Avg Response Time (min)",
    )
    success_rate: float = fields.Float(
        compute="_compute_totals",
        string="Success Rate (%)",
    )

    # Document type breakdown
    fe_count: int = fields.Integer(compute="_compute_by_type")
    afe_count: int = fields.Integer(compute="_compute_by_type")
    nce_count: int = fields.Integer(compute="_compute_by_type")
    nde_count: int = fields.Integer(compute="_compute_by_type")
    nre_count: int = fields.Integer(compute="_compute_by_type")

    # Batch job stats
    active_batches: int = fields.Integer(
        compute="_compute_batch_stats",
        string="Active Batches",
    )
    batch_success_rate: float = fields.Float(
        compute="_compute_batch_stats",
        string="Batch Success Rate (%)",
    )

    # Contingency stats
    contingency_pending: int = fields.Integer(
        compute="_compute_contingency_stats",
        string="Contingency Pending Sync",
    )

    company_id: Company = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @api.depends()
    def _compute_totals(self) -> None:
        """Compute overall KPI numbers."""
        for rec in self:
            company = rec.company_id or self.env.company
            today = fields.Date.context_today(self)

            # Base domain
            domain = [("company_id", "=", company.id)]

            # Counts
            all_docs = self.env["account.move"].search(domain)
            rec.total_documents = len(all_docs)
            rec.pending_send = len(
                all_docs.filtered(lambda d: d.l10n_py_edi_status == "to_send")
            )
            rec.sent_pending_response = len(
                all_docs.filtered(lambda d: d.l10n_py_edi_status in ("sent", "pending"))
            )

            accepted_today_domain = domain + [
                ("l10n_py_edi_accepted_date", ">=", today),
                ("l10n_py_edi_status", "=", "accepted"),
            ]
            accepted_today = self.env["account.move"].search(accepted_today_domain)
            rec.accepted_today = len(accepted_today)

            rejected_today_domain = domain + [
                ("write_date", ">=", today),
                ("l10n_py_edi_status", "=", "rejected"),
            ]
            rejected_today = self.env["account.move"].search(rejected_today_domain)
            rec.rejected_today = len(rejected_today)

            # Week/month
            week_start = today - fields.Date.relativedelta(days=today.weekday())
            month_start = today.replace(day=1)

            rec.accepted_this_week = len(
                self.env["account.move"].search(
                    domain
                    + [
                        ("l10n_py_edi_status", "=", "accepted"),
                        ("l10n_py_edi_accepted_date", ">=", week_start),
                    ]
                )
            )
            rec.accepted_this_month = len(
                self.env["account.move"].search(
                    domain
                    + [
                        ("l10n_py_edi_status", "=", "accepted"),
                        ("l10n_py_edi_accepted_date", ">=", month_start),
                    ]
                )
            )

            # Success rate
            total_sent = len(
                all_docs.filtered(
                    lambda d: d.l10n_py_edi_status in ("accepted", "rejected")
                )
            )
            if total_sent > 0:
                rec.success_rate = round((len(accepted_today) / total_sent) * 100, 1)
            else:
                rec.success_rate = 0.0
            rec.avg_response_time = 0.0

    @api.depends()
    def _compute_by_type(self) -> None:
        """Compute document type breakdown."""
        for rec in self:
            company = rec.company_id or self.env.company
            docs = self.env["account.move"].search(
                [
                    ("company_id", "=", company.id),
                    ("l10n_py_edi_status", "=", "accepted"),
                ]
            )

            # Count by document type
            # Type 1=FE, 4=AFE, 5=NCE, 6=NDE, 7=NRE
            rec.fe_count = len(
                docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "1")
            )
            rec.afe_count = len(
                docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "4")
            )
            rec.nce_count = len(
                docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "5")
            )
            rec.nde_count = len(
                docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "6")
            )
            rec.nre_count = len(
                docs.filtered(lambda d: d.l10n_latam_document_type_id.code == "7")
            )

    @api.depends()
    def _compute_batch_stats(self) -> None:
        """Compute batch job statistics."""
        for rec in self:
            company = rec.company_id or self.env.company
            active = self.env["l10n_py.batch.job"].search(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ["queued", "running"]),
                ]
            )
            rec.active_batches = len(active)

            # Success rate from done batches
            done = self.env["l10n_py.batch.job"].search(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ["done", "partial"]),
                ]
            )
            if done:
                total_success = sum(done.mapped("done_count") or [0])
                total = sum(done.mapped("total_count") or [0])
                if total > 0:
                    rec.batch_success_rate = round((total_success / total) * 100, 1)
                else:
                    rec.batch_success_rate = 0.0
            else:
                rec.batch_success_rate = 0.0

    @api.depends()
    def _compute_contingency_stats(self) -> None:
        """Compute contingency mode statistics."""
        for rec in self:
            company = rec.company_id or self.env.company
            rec.contingency_pending = len(
                self.env["account.move"].search(
                    [
                        ("company_id", "=", company.id),
                        ("l10n_py_edi_status", "=", "contingency_pending"),
                    ]
                )
            )

    def action_open_pending_documents(self) -> dict:
        """Open list of pending documents."""
        return {
            "type": "ir.actions.act_window",
            "name": "Pending EDI Documents",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("l10n_py_edi_status", "in", ["to_send", "sent", "pending"]),
            ],
            "context": {"search_default_l10n_py_edi_status_to_send": 1},
        }

    def action_open_rejected_documents(self) -> dict:
        """Open list of rejected documents."""
        return {
            "type": "ir.actions.act_window",
            "name": "Rejected EDI Documents",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("l10n_py_edi_status", "=", "rejected")],
        }

    def action_open_contingency_documents(self) -> dict:
        """Open list of contingency pending documents."""
        return {
            "type": "ir.actions.act_window",
            "name": "Contingency Pending Sync",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("l10n_py_edi_status", "=", "contingency_pending")],
        }
