# l10n_py_edi_base/models/edi_logging_mixin.py

"""
Automatic EDI Operations Logging Mixin
Facilita o logging consistente em todos os conectores
"""

import logging
import time
from contextlib import contextmanager

from odoo import models

_logger = logging.getLogger(__name__)


class EDILoggingMixin(models.AbstractModel):
    """Automatic EDI operations logging mixin"""

    _name = "l10n_py.edi.logging.mixin"
    _description = "Automatic EDI Logging Mixin"

    @contextmanager
    def log_edi_operation(self, operation_type, provider, document=None, **kwargs):
        """
        Context manager for automatic EDI operations logging

        Usage:
            with self.log_edi_operation('send', 'factpy', document) as log_data:
                result = self.send_to_provider(data)
                log_data['response_data'] = result

        Args:
            operation_type (str): Tipo de operação
            provider (str): Provedor EDI
            document (account.move): Document relacionado
            **kwargs: Dados adicionais para o log

        Yields:
            dict: Dictionary to add data during the operation
        """
        start_time = time.time()
        log_data = {
            "operation_type": operation_type,
            "provider": provider,
            "document": document,
            **kwargs,
        }

        try:
            # Executar operação
            yield log_data

            # Operação bem-sucedida
            execution_time = (time.time() - start_time) * 1000
            self.env["l10n_py.edi.log"].log_operation(
                execution_time=execution_time, success=True, **log_data
            )

        except Exception as exc:
            # Operação com erro
            execution_time = (time.time() - start_time) * 1000
            try:
                self.env["l10n_py.edi.log"].log_operation(
                    execution_time=execution_time,
                    success=False,
                    error_message=str(exc),
                    **log_data,
                )
            except Exception:
                _logger.warning("Failed to log EDI operation: %s", exc, exc_info=True)
            # Re-raise a exceção original
            raise exc

    def _log_success(
        self, operation_type, provider, document=None, execution_time=0, **kwargs
    ):
        """
        Log de operação bem-sucedida

        Args:
            operation_type (str): Tipo de operação
            provider (str): Provedor EDI
            document (account.move): Document relacionado
            execution_time (float): Tempo de execução em ms
            **kwargs: Dados adicionais
        """
        return self.env["l10n_py.edi.log"].log_operation(
            operation_type=operation_type,
            provider=provider,
            document=document,
            execution_time=execution_time,
            success=True,
            **kwargs,
        )

    def _log_error(
        self,
        operation_type,
        provider,
        error_message,
        document=None,
        execution_time=0,
        **kwargs,
    ):
        """
        Log de operação com erro

        Args:
            operation_type (str): Tipo de operação
            provider (str): Provedor EDI
            error_message (str): Mensagem de erro
            document (account.move): Document relacionado
            execution_time (float): Tempo de execução em ms
            **kwargs: Dados adicionais
        """
        return self.env["l10n_py.edi.log"].log_operation(
            operation_type=operation_type,
            provider=provider,
            document=document,
            execution_time=execution_time,
            success=False,
            error_message=error_message,
            **kwargs,
        )
