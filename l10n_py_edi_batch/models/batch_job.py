# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from odoo import api, fields, models

if TYPE_CHECKING:
    from odoo.addons.account.models import AccountMove
    from odoo.addons.base.models.res_company import Company
    from odoo.addons.base.models.res_users import Users

_logger = logging.getLogger(__name__)

# Batch size limit per pysifen enviar_lote
PYSIFEN_BATCH_LIMIT = 50


class BatchJob(models.Model):
    """Batch job for processing multiple EDI documents at once."""

    _name = "l10n_py.batch.job"
    _description = "EDI Batch Job"
    _order = "create_date desc"
    _check_company_auto = True

    name: str = fields.Char(string="Name", required=True, copy=False)
    company_id: Company = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    state: str = fields.Selection(
        [
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("running", "Running"),
            ("done", "Done"),
            ("partial", "Partial Success"),
            ("failed", "Failed"),
        ],
        string="State",
        default="draft",
        readonly=True,
        copy=False,
    )
    batch_type: str = fields.Selection(
        [
            ("send", "Send Documents"),
            ("status_check", "Check Status"),
            ("cancel", "Cancel Documents"),
        ],
        string="Batch Type",
        required=True,
        default="send",
    )
    move_ids: AccountMove = fields.Many2many(
        "account.move",
        string="Invoices",
        help="Invoices included in this batch",
    )
    line_ids: models.Model = fields.One2many(
        "l10n_py.batch.job.line",
        "job_id",
        string="Lines",
        copy=False,
    )
    batch_size: int = fields.Integer(
        string="Batch Size",
        default=50,
        help="Maximum documents sent per batch call (pysifen limit: 50)",
    )
    total_count: int = fields.Integer(
        string="Total",
        compute="_compute_counts",
        store=True,
    )
    done_count: int = fields.Integer(
        string="Done",
        compute="_compute_counts",
        store=True,
    )
    failed_count: int = fields.Integer(
        string="Failed",
        compute="_compute_counts",
        store=True,
    )
    pending_count: int = fields.Integer(
        string="Pending",
        compute="_compute_counts",
        store=True,
    )
    progress: float = fields.Float(
        string="Progress (%)",
        compute="_compute_counts",
        store=True,
        digits=(5, 2),
    )
    started_at: fields.Datetime = fields.Datetime(string="Started At", copy=False)
    finished_at: fields.Datetime = fields.Datetime(string="Finished At", copy=False)
    error_message: str = fields.Text(string="Error Message", copy=False)
    user_id: Users = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    @api.depends("line_ids.state")
    def _compute_counts(self) -> None:
        """Compute counts from job lines."""
        for job in self:
            lines = job.line_ids
            job.total_count = len(lines)
            job.done_count = len(lines.filtered(lambda rec: rec.state == "success"))
            job.failed_count = len(lines.filtered(lambda rec: rec.state == "failed"))
            job.pending_count = len(lines.filtered(lambda rec: rec.state == "pending"))
            job.progress = (
                (job.done_count + job.failed_count) / job.total_count * 100
                if job.total_count > 0
                else 0.0
            )

    def action_queue(self) -> bool:
        """Set job to queued state and create lines.

        Returns:
            True on success.
        """
        self.ensure_one()
        if self.state != "draft":
            return False
        self._create_lines()
        self.write({"state": "queued"})
        return True

    def _create_lines(self) -> None:
        """Create batch job lines from selected moves."""
        self.ensure_one()
        # Remove existing lines
        self.line_ids.unlink()
        vals = []
        for move in self.move_ids:
            vals.append(
                {
                    "job_id": self.id,
                    "move_id": move.id,
                    "state": "pending",
                    "attempts": 0,
                }
            )
        if vals:
            self.env["l10n_py.batch.job.line"].create(vals)

    def action_run(self) -> bool | None:
        """Process batch job based on batch_type.

        Returns:
            True on success, None on failure.
        """
        self.ensure_one()
        if self.state not in ("queued", "draft"):
            return None
        self.write({"state": "running", "started_at": fields.Datetime.now()})

        try:
            if self.batch_type == "send":
                self._process_send_batch()
            elif self.batch_type == "status_check":
                self._process_status_batch()
            elif self.batch_type == "cancel":
                self._process_cancel_batch()
        except Exception as e:
            self.write({"state": "failed", "error_message": str(e)})
            _logger.exception("Batch job %s failed: %s", self.name, str(e))
            return None

        self._finalize_job()
        return True

    def _process_send_batch(self) -> None:  # noqa: C901
        """Send documents via pysifen enviar_lote."""
        try:
            import pysifen.transmissao  # noqa: F401
        except ImportError:
            _logger.warning("pysifen not installed, skipping batch send")
            return

        pending = self.line_ids.filtered(lambda rec: rec.state == "pending")
        if not pending:
            return

        connector = self._get_connector()
        if not connector:
            for line in pending:
                line.write(
                    {
                        "state": "failed",
                        "error_message": "No EDI connector configured",
                        "attempts": 1,
                        "last_attempt": fields.Datetime.now(),
                    }
                )
            return

        batch_size = min(self.batch_size or 50, PYSIFEN_BATCH_LIMIT)
        sent = 0

        while True:
            batch_lines = pending.filtered(lambda rec: rec.state == "pending")[
                :batch_size
            ]
            if not batch_lines:
                break

            # Build RDe list
            rdes = []
            for line in batch_lines:
                try:
                    rde = connector._sifen_build_rde(
                        line.move_id._prepare_edi_document_data()
                    )
                    rdes.append(rde)
                except Exception as e:
                    line.write(
                        {
                            "state": "failed",
                            "error_message": str(e),
                            "attempts": line.attempts + 1,
                            "last_attempt": fields.Datetime.now(),
                        }
                    )
                    # Remove from batch if failed to build
                    batch_lines -= line

            if not rdes:
                break

            # Send batch
            try:
                transmissao = connector._sifen_get_transmissao_de()
                result = transmissao.enviar_lote(rdes, sign=True)

                # Process results
                for i, line in enumerate(batch_lines):
                    if line.state != "pending":
                        continue
                    if i >= len(result.resultados):
                        line.write(
                            {
                                "state": "failed",
                                "error_message": (
                                    f"pysifen returned {len(result.resultados)} "
                                    f"results for {len(batch_lines)} batch lines"
                                ),
                                "attempts": line.attempts + 1,
                                "last_attempt": fields.Datetime.now(),
                            }
                        )
                        sent += 1
                        continue
                    res = result.resultados[i]
                    if res.get("exitoso", False):
                        line.write(
                            {
                                "state": "success",
                                "attempts": line.attempts + 1,
                                "last_attempt": fields.Datetime.now(),
                            }
                        )
                        # Process EDI response
                        try:
                            line.move_id._process_edi_response(res)
                        except Exception as exc:
                            _logger.warning(
                                "Failed to process EDI response for move %s: %s",
                                line.move_id.name,
                                str(exc),
                            )
                    else:
                        line.write(
                            {
                                "state": "failed",
                                "error_message": res.get(
                                    "mensaje_respuesta", "Unknown error"
                                ),
                                "attempts": line.attempts + 1,
                                "last_attempt": fields.Datetime.now(),
                            }
                        )
                    sent += 1

            except Exception as e:
                _logger.error("Batch send error: %s", str(e))
                for line in batch_lines:
                    if line.state == "pending":
                        line.write(
                            {
                                "state": "failed",
                                "error_message": str(e),
                                "attempts": line.attempts + 1,
                                "last_attempt": fields.Datetime.now(),
                            }
                        )

        _logger.info("Batch job %s: sent %d documents", self.name, sent)

    def _process_status_batch(self) -> None:
        """Check status of documents in batch."""
        pending = self.line_ids.filtered(lambda rec: rec.state == "pending")
        connector = self._get_connector()

        if not connector:
            for line in pending:
                line.write(
                    {
                        "state": "failed",
                        "error_message": "No EDI connector configured",
                        "attempts": 1,
                        "last_attempt": fields.Datetime.now(),
                    }
                )
            return

        for line in pending:
            try:
                if not line.move_id.l10n_py_cdc:
                    line.write(
                        {
                            "state": "failed",
                            "error_message": "Document has no CDC",
                            "attempts": line.attempts + 1,
                            "last_attempt": fields.Datetime.now(),
                        }
                    )
                    continue

                result = connector._sifen_check_status(line.move_id.l10n_py_cdc)
                if result.get("success"):
                    line.move_id._update_edi_status_from_response(result)
                    line.write(
                        {
                            "state": "success",
                            "attempts": line.attempts + 1,
                            "last_attempt": fields.Datetime.now(),
                        }
                    )
                else:
                    line.write(
                        {
                            "state": "failed",
                            "error_message": result.get("error", "Unknown error"),
                            "attempts": line.attempts + 1,
                            "last_attempt": fields.Datetime.now(),
                        }
                    )
            except Exception as e:
                line.write(
                    {
                        "state": "failed",
                        "error_message": str(e),
                        "attempts": line.attempts + 1,
                        "last_attempt": fields.Datetime.now(),
                    }
                )

    def _process_cancel_batch(self) -> None:
        """Cancel documents in batch."""
        pending = self.line_ids.filtered(lambda rec: rec.state == "pending")
        connector = self._get_connector()

        if not connector:
            for line in pending:
                line.write(
                    {
                        "state": "failed",
                        "error_message": "No EDI connector configured",
                        "attempts": 1,
                        "last_attempt": fields.Datetime.now(),
                    }
                )
            return

        for line in pending:
            try:
                result = connector._sifen_cancel_document(line.move_id)
                if result.get("success"):
                    line.write(
                        {
                            "state": "success",
                            "attempts": line.attempts + 1,
                            "last_attempt": fields.Datetime.now(),
                        }
                    )
                else:
                    line.write(
                        {
                            "state": "failed",
                            "error_message": result.get("error", "Unknown error"),
                            "attempts": line.attempts + 1,
                            "last_attempt": fields.Datetime.now(),
                        }
                    )
            except Exception as e:
                line.write(
                    {
                        "state": "failed",
                        "error_message": str(e),
                        "attempts": line.attempts + 1,
                        "last_attempt": fields.Datetime.now(),
                    }
                )

    def _finalize_job(self) -> None:
        """Set final state based on line results."""
        self.ensure_one()
        self.write({"finished_at": fields.Datetime.now()})

        if not self.line_ids:
            self.write({"state": "failed", "error_message": "No lines to process"})
            return

        pending = self.line_ids.filtered(lambda rec: rec.state == "pending")
        failed = self.line_ids.filtered(lambda rec: rec.state == "failed")

        if not pending and not failed:
            self.write({"state": "done"})
        elif not pending and failed:
            self.write({"state": "partial"})
        elif pending and failed:
            self.write({"state": "partial"})

    def action_retry_failed(self) -> bool | None:
        """Reset failed lines to pending for retry.

        Returns:
            True on success, None if state doesn't allow retry.
        """
        self.ensure_one()
        if self.state not in ("partial", "failed", "done"):
            return None
        self.line_ids.filtered(lambda rec: rec.state == "failed").write(
            {"state": "pending", "error_message": False}
        )
        self.write({"state": "queued", "error_message": False})
        return self.action_run()

    def _get_connector(self, company: Company | None = None) -> models.Model | bool:
        """Get EDI connector for company.

        Args:
            company: Company to get connector for. Defaults to self.company_id.

        Returns:
            EDI connector record or False if not found.
        """
        company = company or self.company_id
        connector = (
            self.env["l10n_py.edi.connector"]
            .sudo()
            .search([("company_id", "=", company.id)], limit=1)
        )
        return connector

    @api.model
    def _cron_process_queued_jobs(self) -> None:
        """Process all queued batch jobs (called by cron)."""
        queued = self.search([("state", "=", "queued")], limit=10)
        for job in queued:
            try:
                job.action_run()
            except Exception as e:
                job.write({"state": "failed", "error_message": str(e)})
                _logger.exception("Cron batch job %s failed: %s", job.name, str(e))


class BatchJobLine(models.Model):
    """Individual line in a batch job."""

    _name = "l10n_py.batch.job.line"
    _description = "Batch Job Line"
    _rec_name = "move_id"
    _order = "sequence, id"
    _check_company_auto = True

    job_id: BatchJob = fields.Many2one(
        "l10n_py.batch.job",
        string="Batch Job",
        required=True,
        ondelete="cascade",
        index=True,
    )
    move_id: AccountMove = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        ondelete="cascade",
    )
    state: str = fields.Selection(
        [
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        string="State",
        default="pending",
        readonly=True,
        copy=False,
    )
    error_message: str = fields.Text(string="Error Message", copy=False)
    attempts: int = fields.Integer(string="Attempts", default=0, readonly=True)
    last_attempt: fields.Datetime = fields.Datetime(string="Last Attempt", copy=False)
    sequence: int = fields.Integer(string="Sequence", default=0)

    @api.model
    def create(self, vals_list: list[dict[str, Any]]) -> BatchJobLine:
        """Auto-assign sequence on creation.

        Args:
            vals_list: List of values for records to create.

        Returns:
            Created batch job lines.
        """
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if "sequence" not in vals:
                last = self.search([], order="sequence desc", limit=1)
                vals["sequence"] = (last.sequence or 0) + 1
        return super().create(vals_list)
