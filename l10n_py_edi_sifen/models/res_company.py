# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_py_certificate = fields.Binary("PKCS12 Certificate (.pfx)")
    l10n_py_certificate_filename = fields.Char()
    l10n_py_certificate_password = fields.Char("Certificate Password")
    l10n_py_certificate_expiry = fields.Date("Expiry Date", readonly=True)

    def _get_pkcs12_data(self):
        """Return (cert_bytes, password) for SIFEN mTLS."""
        self.ensure_one()
        if not self.l10n_py_certificate:
            raise UserError(
                self.env._("Configure the PKCS12 certificate in company %s", self.name)
            )
        cert_bytes = base64.b64decode(self.l10n_py_certificate)
        return cert_bytes, self.l10n_py_certificate_password or ""
