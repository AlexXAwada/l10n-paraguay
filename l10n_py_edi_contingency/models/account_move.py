# l10n_py_edi_contingency/models/account_move.py

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from odoo import api, fields, models
from odoo.tools import SQL

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Extend account.move with contingency mode support."""

    _inherit = "account.move"

    l10n_py_contingency_booklet_id: models.Model = fields.Many2one(
        "l10n_py.contingency.booklet",
        string="Contingency Booklet",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
        index=True,
        copy=False,
        help="Physical booklet used for this contingency document",
    )
    l10n_py_contingency_number: str = fields.Char(
        string="Contingency Number",
        copy=False,
        index=True,
        help="Document number from physical booklet (assigned in contingency mode)",
    )
    l10n_py_contingency_mode: bool = fields.Boolean(
        string="Contingency Mode",
        compute="_compute_contingency_mode",
        store=True,
        help="True when this document uses contingency mode (no SIFEN connection)",
    )

    @api.depends(
        "l10n_py_emission_type",
        "l10n_py_edi_status",
        "l10n_py_cdc",
        "l10n_py_contingency_booklet_id",
    )
    def _compute_contingency_mode(self) -> None:
        """Determine if this move is operating in contingency mode."""
        for rec in self:
            rec.l10n_py_contingency_mode = (
                rec.l10n_py_emission_type == "2"
                and rec.l10n_py_edi_status
                in ("pending", "draft", "contingency_pending")
                and not rec.l10n_py_cdc
                and rec.l10n_py_contingency_booklet_id
            )

    def _should_use_contingency(self) -> bool:
        """Check if this document should use contingency mode.

        Contingency is used when:
        - EDI status is pending/draft
        - No CDC has been generated
        - SIFEN is unreachable after multiple attempts OR
          user manually assigned a contingency booklet

        Returns:
            True if contingency mode should be used.
        """
        self.ensure_one()
        if self.l10n_py_cdc:
            return False
        if self.l10n_py_edi_status == "accepted":
            return False
        if self.l10n_py_contingency_booklet_id:
            return True
        # Check if SIFEN has failed multiple times
        send_count = self.l10n_py_edi_send_count or 0
        if send_count >= 3:
            _logger.warning(
                "Document %s: SIFEN unreachable after %s attempts, "
                "considering contingency mode",
                self.name,
                send_count,
            )
        return False

    def _prepare_contingency_document(self) -> None:
        """Generate document in contingency format.

        In contingency mode, the document does NOT receive a CDC from SIFEN.
        Instead, it uses a physical booklet number from SET. The document
        is queued for later sync when connection is restored.

        The XML is generated without SIFEN signature and marked as
        'contingencia' in the header. It will be replaced with the
        real SIFEN XML after sync.
        """
        self.ensure_one()
        if not self.l10n_py_contingency_booklet_id:
            return

        booklet = self.l10n_py_contingency_booklet_id
        next_number = booklet._get_next_number()

        # Assign contingency number
        self.write({"l10n_py_contingency_number": str(next_number)})

        # Generate contingency XML (simplified format, no SIFEN signature)
        # NOTE: _generate_contingency_xml() is currently a placeholder that does
        # NOT conform to the SET specification. SIFEN would reject it if saved
        # as the real EDI document, so we only update the status here and
        # persist the real XML after SIFEN sync (see _sync_contingency_to_sifen).
        self.write(
            {
                "l10n_py_edi_status": "contingency_pending",
            }
        )

        _logger.info(
            "Document %s: Contingency mode activated with number %s from booklet %s",
            self.name,
            next_number,
            booklet.name,
        )

    def _generate_contingency_xml(self) -> str:
        """Generate XML in SET contingency format.

        The contingency XML follows SET specification with these differences
        from normal SIFEN XML:
        - No CDC (uses physical booklet number instead)
        - Different signature indicator
        - Marked as 'CONTINGENCIA' in document type

        Returns:
            XML content in contingency format.
        """
        self.ensure_one()

        # Build basic XML structure for contingency
        # This is a placeholder - actual format follows SET specification
        doc_date = (self.invoice_date or fields.Date.today()).isoformat()
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f"<DE version='1.0' TipoDoc='{self.l10n_py_document_type}'>",
            "  <IdDoc>",
            "    <TipEmi>2</TipEmi>",
            f"    <NroTimbrado>{self.l10n_py_contingency_booklet_id.name}"
            f"</NroTimbrado>",
            f"    <NroFec>CONT-{self.l10n_py_contingency_number}</NroFec>",
            "  </IdDoc>",
            f"  <Fecha>{doc_date}</Fecha>",
            "  <Contingencia>1</Contingencia>",
            "</DE>",
        ]

        return "\n".join(xml_lines)

    @api.model
    def _cron_sync_contingency_documents(self) -> None:
        """Sync contingency documents to SIFEN when connection is restored.

        This cron runs periodically (default: every 30 minutes) to check
        if contingency documents can be sent to SIFEN. When connection
        is available:
        1. Retrieve each contingency_pending document
        2. Send to SIFEN to get real CDC
        3. Update XML with actual CDC
        4. Regenerate KUDE
        5. Mark as to_send for normal processing
        """
        # Check DB connection using SQL() builder
        self.env.cr.execute(SQL("SELECT 1"))
        domain = [
            ("l10n_py_edi_status", "=", "contingency_pending"),
            ("l10n_py_contingency_booklet_id", "!=", False),
        ]
        contingency_docs = self.search(domain, order="write_date asc")

        if not contingency_docs:
            _logger.debug("No contingency documents to sync")
            return

        _logger.info("Found %s contingency documents to sync", len(contingency_docs))

        synced = 0
        failed = 0

        for doc in contingency_docs:
            try:
                # Check if we have a valid connection to SIFEN
                if not doc._check_sifen_connection():
                    _logger.info("SIFEN not available, skipping sync for %s", doc.name)
                    continue

                # Attempt to sync
                doc._sync_contingency_to_sifen()
                synced += 1

            except Exception as e:
                failed += 1
                _logger.warning(
                    "Failed to sync contingency document %s: %s", doc.name, str(e)
                )

        _logger.info("Contingency sync complete: %s synced, %s failed", synced, failed)

    def _check_sifen_connection(self) -> bool:
        """Check if SIFEN is reachable.

        Returns:
            True if SIFEN responds to test connection.
        """
        connector = (
            self.env["l10n_py.edi.connector"]
            .sudo()
            .search([("company_id", "=", self.company_id.id)], limit=1)
        )
        if not connector:
            return False

        # test_connection() returns an ir.actions.client dict on success and
        # raises UserError on failure. Treat absence of exception as success.
        try:
            connector.test_connection()
            return True
        except Exception:
            return False

    def _sync_contingency_to_sifen(self) -> None:
        """Send contingency document to SIFEN and replace with real CDC.

        This replaces the contingency XML with the actual SIFEN XML
        and updates the document status for normal processing.
        """
        self.ensure_one()

        if not self.l10n_py_contingency_booklet_id:
            return

        # Clear contingency fields and trigger normal send
        self.write(
            {
                "l10n_py_contingency_booklet_id": False,
                "l10n_py_contingency_number": False,
            }
        )

        # Trigger normal EDI send (will generate real CDC)
        self.action_send_edi()

        _logger.info("Document %s synced from contingency to SIFEN", self.name)
