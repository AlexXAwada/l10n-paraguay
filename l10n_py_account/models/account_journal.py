# l10n_py_account/models/account_journal.py

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # ============== PARAGUAY EDI FIELDS ==============

    l10n_py_establishment = fields.Char(
        string="Establishment",
        size=3,
        default="001",
        help="Establishment code (3 digits)",
    )

    l10n_py_point = fields.Char(
        string="Expedition Point",
        size=3,
        default="001",
        help="Expedition point code (3 digits)",
    )

    l10n_py_authorization_id = fields.Many2one(
        "account.authorization",
        string="Authorization",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help="Authorization issued by SET for this journal",
    )

    l10n_py_authorization_validity = fields.Date(
        string="Authorization Expiry",
        related="l10n_py_authorization_id.date_to",
        store=True,
        readonly=True,
        help="Authorization expiry date",
    )

    # ============== CONSTRAINT METHODS ==============

    @api.constrains("l10n_py_establishment")
    def _check_establishment(self):
        """Validate establishment format"""
        for journal in self:
            if journal.l10n_py_establishment:
                if not journal.l10n_py_establishment.isdigit():
                    raise ValidationError(
                        self.env._("The establishment must be numeric")
                    )
                if len(journal.l10n_py_establishment) != 3:
                    raise ValidationError(
                        self.env._("The establishment must have 3 digits")
                    )

    @api.constrains("l10n_py_point")
    def _check_point(self):
        """Validate expedition point format"""
        for journal in self:
            if journal.l10n_py_point:
                if not journal.l10n_py_point.isdigit():
                    raise ValidationError(
                        self.env._("The expedition point must be numeric")
                    )
                if len(journal.l10n_py_point) != 3:
                    raise ValidationError(
                        self.env._("The expedition point must have 3 digits")
                    )

    @api.constrains("l10n_py_authorization_id")
    def _check_timbrado_consistency(self):
        """Validate authorization consistency with establishment and point"""
        for journal in self:
            if journal.l10n_py_authorization_id:
                if (
                    journal.l10n_py_authorization_id.establishment
                    != journal.l10n_py_establishment
                    or journal.l10n_py_authorization_id.expedition_point
                    != journal.l10n_py_point
                ):
                    raise ValidationError(
                        self.env._(
                            "The selected authorization does not match the "
                            "establishment and expedition point "
                            "configured on the journal."
                        )
                    )
