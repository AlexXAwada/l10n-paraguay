# l10n_py_edi_base/models/l10n_py_edi_log.py

"""
Advanced Logging System for EDI Operations
Implements complete logging per improvement proposals
"""

import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EDILog(models.Model):
    """Robust model to register EDI operation logs"""

    _name = "l10n_py.edi.log"
    _description = "EDI Operations Log"
    _order = "create_date desc"
    _rec_name = "operation_type"

    # ============== OPERATION IDENTIFICATION ==============

    operation_type = fields.Selection(
        [
            ("send", "Document Sending"),
            ("status", "Status Check"),
            ("cancel", "Cancellation"),
            ("event", "Event"),
            ("webhook", "Webhook"),
            ("inutilize", "Number Inutilization"),
            ("download_pdf", "Download PDF"),
            ("download_xml", "Download XML"),
            ("validate", "Validation"),
        ],
        required=True,
        index=True,
    )

    # ============== RELATED DOCUMENTS ==============

    document_id = fields.Many2one(
        "account.move",
        ondelete="cascade",
        index=True,
        help="Related fiscal document",
    )

    cdc = fields.Char(index=True, help="Document control code")

    # ============== EDI PROVIDER ==============

    provider = fields.Selection(
        [
            ("factpy", "FactPy"),
            ("facturasend", "InvoiceSend"),
            ("sifen", "SIFEN Directo"),
            ("local", "Local Processing"),
        ],
        required=True,
        index=True,
    )

    # ============== REQUEST DATA ==============

    endpoint = fields.Char(help="API URL or endpoint")

    method = fields.Selection(
        [
            ("GET", "GET"),
            ("POST", "POST"),
            ("PUT", "PUT"),
            ("DELETE", "DELETE"),
            ("PATCH", "PATCH"),
        ],
    )

    request_headers = fields.Text(help="HTTP headers sent")

    request_data = fields.Text(help="Request payload")

    # ============== RESPONSE DATA ==============

    status_code = fields.Integer(help="HTTP status code")

    response_headers = fields.Text(help="HTTP headers received")

    response_data = fields.Text(help="Response payload")

    # ============== METRICS ==============

    execution_time = fields.Float(
        help="Execution time in milliseconds",
        digits=(10, 2),
    )

    # ============== STATUS AND ERROR ==============

    success = fields.Boolean(
        default=True,
        index=True,
        help="Indicates whether the operation was successful",
    )

    error_message = fields.Text(help="Error description if any")

    error_code = fields.Char(help="Provider error code")

    # ============== ADDITIONAL DATA ==============

    batch_id = fields.Char(help="Provider batch identifier")

    retry_count = fields.Integer(default=0, help="Number of retries performed")

    # ============== COMPUTED FIELDS ==============

    error = fields.Boolean(
        compute="_compute_error",
        store=True,
        help="Indicates whether there was an error in the operation",
    )

    duration_human = fields.Char(
        compute="_compute_duration_human",
        help="Duration in readable format",
    )

    # ============== COMPUTE METHODS ==============

    @api.depends("status_code", "success")
    def _compute_error(self):
        """Compute if it is an error based on status code and success flag"""
        for record in self:
            if record.status_code:
                record.error = record.status_code >= 400
            else:
                record.error = not record.success

    @api.depends("execution_time")
    def _compute_duration_human(self):
        """Format duration for display"""
        for record in self:
            if record.execution_time:
                if record.execution_time < 1000:
                    record.duration_human = f"{int(record.execution_time)} ms"
                else:
                    seconds = record.execution_time / 1000
                    record.duration_human = f"{round(seconds, 2)} s"
            else:
                record.duration_human = "N/A"

    # ============== PUBLIC METHODS ==============

    @api.model
    def log_operation(
        self,
        operation_type,
        provider,
        document=None,
        request_data=None,
        response_data=None,
        execution_time=0,
        success=True,
        error_message=None,
        **kwargs,
    ):
        """
        Register EDI operation

        Args:
            operation_type (str): Operation type
            provider (str): EDI provider
            document (account.move): Related document
            request_data (dict): Request data
            response_data (dict): Response data
            execution_time (float): Execution time in ms
            success (bool): Whether the operation was successful
            error_message (str): Error message (if any)
            **kwargs: Additional fields

        Returns:
            l10n_py.edi.log: Created log record
        """
        try:
            # Preparar dados do log
            log_vals = {
                "operation_type": operation_type,
                "provider": provider,
                "execution_time": execution_time,
                "success": success,
                "error_message": error_message,
            }

            # Document relacionado
            if document:
                log_vals["document_id"] = document.id
                log_vals["cdc"] = getattr(document, "l10n_py_cdc", False)

            # Dados da requisição
            if request_data:
                if isinstance(request_data, dict):
                    log_vals["request_data"] = json.dumps(
                        request_data, indent=2, ensure_ascii=False
                    )
                else:
                    log_vals["request_data"] = str(request_data)

            # Dados da resposta
            if response_data:
                if isinstance(response_data, dict):
                    response_json = json.dumps(
                        response_data, indent=2, ensure_ascii=False
                    )
                    # Limitar tamanho para evitar problemas
                    log_vals["response_data"] = response_json[:10000]
                else:
                    log_vals["response_data"] = str(response_data)[:10000]

            # Campos adicionais
            for key, value in kwargs.items():
                if key in self._fields:
                    log_vals[key] = value

            # Criar registro de log
            log_record = self.create(log_vals)

            # Also log to system
            if not success:
                _logger.error(
                    f"EDI Error [{provider}] {operation_type}: {error_message}"
                )
            else:
                _logger.info(
                    f"EDI Success [{provider}] {operation_type} "
                    f"({int(execution_time)}ms)"
                )

            return log_record

        except Exception as e:
            _logger.exception(f"Error creating EDI log: {str(e)}")
            return False

    def action_view_document(self):
        """Open related document"""
        self.ensure_one()
        if not self.document_id:
            return False

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.document_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_retry_operation(self):
        """Retry operation (if applicable)"""
        self.ensure_one()

        if self.operation_type == "send" and self.document_id:
            # Increment retry counter
            self.write({"retry_count": self.retry_count + 1})
            return self.document_id.action_send_edi()

        return False

    def action_view_request_data(self):
        """Display request data in readable format"""
        self.ensure_one()
        return self._show_data_wizard("request", self.request_data)

    def action_view_response_data(self):
        """Display response data in readable format"""
        self.ensure_one()
        return self._show_data_wizard("response", self.response_data)

    def _show_data_wizard(self, data_type, data):
        """Show wizard with formatted data"""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._(
                    "Data for %(data_type)s", data_type=data_type.capitalize()
                ),
                "message": data or self.env._("No data"),
                "type": "info",
                "sticky": True,
            },
        }
