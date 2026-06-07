# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SIFENWebhookController(http.Controller):
    """Webhook endpoint to receive async responses from SIFEN.

    SIFEN sends webhook notifications when document status changes
    (e.g., from 'sent' to 'accepted' or 'rejected').
    """

    @http.route(
        "/l10n_py_edi/webhook/<int:company_id>",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def receive_sifen_response(self, company_id):
        """Receive and process SIFEN webhook notification.

        :param int company_id: ID of the company to route the response to.
        :returns: dict with 'success' boolean and optional 'message'.
        """
        # Verify request has payload — use get_json_data for raw JSON body
        try:
            json_data = request.get_json_data()
        except Exception:
            json_data = {}
        _logger.info(
            "Webhook received: company=%s, json_data=%s, params=%s",
            company_id,
            json_data,
            dict(request.params),
        )
        if not json_data:
            _logger.warning("Webhook received empty payload from SIFEN")
            return {"success": False, "message": "Empty payload"}

        # Verify webhook token (Bearer token in Authorization header)
        auth_header = request.httprequest.headers.get("Authorization", "")
        if not self._verify_webhook_token(company_id, auth_header, json_data):
            _logger.warning(
                "Webhook rejected: invalid token for company %s", company_id
            )
            return {"success": False, "message": "Unauthorized"}

        # Extract CDC from payload (SIFEN uses different field names)
        cdc = (
            json_data.get("cdc")
            or json_data.get("CDC")
            or json_data.get("codigoControl")
            or json_data.get("codigo_control")
        )
        batch_id = json_data.get("lote") or json_data.get("batch_id")

        # Find the document
        move = self._find_document_by_cdc(company_id, cdc)
        if not move and batch_id:
            move = self._find_document_by_batch_id(company_id, batch_id)

        if not move:
            _logger.warning(
                "Webhook: no document found for CDC=%s, batch=%s",
                cdc,
                batch_id,
            )
            return {"success": False, "message": "Document not found"}

        # Process the response
        try:
            self._process_webhook_response(move, json_data)
        except Exception as e:
            _logger.error("Error processing webhook for move %s: %s", move.name, str(e))
            return {"success": False, "message": str(e)}

        return {"success": True, "message": "OK"}

    def _verify_webhook_token(self, company_id, auth_header, json_data):
        """Verify the webhook request token.

        Security: In production, this should validate against the company
        configured webhook token or verify against SIFEN's IP whitelist.
        For now, we accept requests with a valid Authorization header
        and verify the token is configured in the company settings.

        :param int company_id: Company ID to validate token for.
        :param str auth_header: Authorization header value (Bearer <token>).
        :param dict json_data: JSON payload (used for fallback token check).
        :returns: True if token is valid, False otherwise.
        """
        # Parse Bearer token
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        elif auth_header:
            token = auth_header

        if not token:
            return False

        # Verify token matches company webhook token
        company = request.env["res.company"].sudo().browse(company_id)
        if not company.exists():
            return False

        webhook_token = company.sudo().l10n_py_webhook_token or ""
        if webhook_token and webhook_token == token:
            return True

        # Fallback: also accept token embedded in payload (some providers do this)
        payload_token = json_data.get("webhook_token") or json_data.get("token", "")
        if payload_token and payload_token == webhook_token:
            return True

        return False

    def _find_document_by_cdc(self, company_id, cdc):
        """Find account.move by CDC number."""
        if not cdc:
            return self.env["account.move"]

        return (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("company_id", "=", company_id),
                    ("l10n_py_cdc", "=", cdc),
                ],
                limit=1,
            )
        )

    def _find_document_by_batch_id(self, company_id, batch_id):
        """Find account.move by batch/transaction ID."""
        if not batch_id:
            return self.env["account.move"]

        return (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("company_id", "=", company_id),
                    ("l10n_py_edi_batch_id", "=", batch_id),
                ],
                limit=1,
            )
        )

    def _process_webhook_response(self, move, json_data):
        """Process the webhook payload and update the document.

        :param recordset move: account.move record to update.
        :param dict json_data: Webhook payload from SIFEN.
        """
        # Extract status from SIFEN response
        # SIFEN sends: estado, codigo, mensaje, cdc, etc.
        estado = (
            json_data.get("estado")
            or json_data.get("state")
            or json_data.get("status", "")
        ).lower()

        # Map SIFEN states to our internal states
        state_map = {
            "aceptado": "accepted",
            "rechazado": "rejected",
            "accepted": "accepted",
            "rejected": "rejected",
            "processing": "processing",
            "enviado": "sent",
            "pendiente": "pending",
        }
        new_status = state_map.get(estado, "sent")

        # Build response dict (same format as connector response)
        response = {
            "success": estado in ("aceptado", "accepted"),
            "estado": new_status,
            "codigo_respuesta": json_data.get("codigo") or json_data.get("code", ""),
            "mensaje_respuesta": json_data.get("mensaje")
            or json_data.get("message", ""),
            "qr": json_data.get("qr") or json_data.get("QR", ""),
            "xml_respuesta": json_data.get("xml"),
        }

        # Update the document
        move._process_edi_response(response)

        # Log the webhook
        self._log_webhook(move, json_data, new_status)

        _logger.info("Webhook processed for %s: status=%s", move.name, new_status)

    def _log_webhook(self, move, json_data, new_status):
        """Log the webhook notification in the EDI log."""
        try:
            self.env["l10n_py.edi.log"].sudo().log_operation(
                operation_type="webhook",
                provider="sifen",
                document=move,
                request_data=json_data,
                success=new_status == "accepted",
                error_message=json_data.get("mensaje") or json_data.get("message"),
            )
        except Exception as e:
            _logger.warning("Failed to log webhook: %s", str(e))
