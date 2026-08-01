# l10n_py_account/models/account_authorization.py
import re
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import ValidationError

MAX_INVOICE_NUMBER = 9999999


class AccountAuthorization(models.Model):
    """
    Model to manage document authorizations (timbrado) from SET Paraguay
    """

    _name = "account.authorization"
    _description = "Document Authorization (Timbrado)"
    _order = "date_from desc, id desc"

    name = fields.Char(
        string="Authorization Number",
        required=True,
        size=8,
        help="Authorization number issued by SET",
    )

    date_from = fields.Date(
        string="Start Date",
        required=True,
        help="Date from which the authorization is valid",
    )

    date_to = fields.Date(
        string="End Date",
        required=True,
        help="Date until which the authorization is valid",
    )

    invoice_number_from = fields.Integer(
        string="From Number",
        required=True,
        help="First authorized invoice number",
    )

    invoice_number_to = fields.Integer(
        string="To Number",
        required=True,
        help="Last authorized invoice number",
    )

    establishment = fields.Char(
        required=True,
        size=3,
        default="001",
        help="Establishment code (3 digits)",
    )

    expedition_point = fields.Char(
        required=True,
        size=3,
        default="001",
        help="Expedition point code (3 digits)",
    )

    series = fields.Char(
        size=2,
        default="AA",
        help="Authorization series (2 uppercase letters, AA-ZZ). "
        "Allows restarting numbering when the range is exhausted.",
    )

    l10n_latam_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Document Type",
        required=True,
        help="LATAM document type (Invoice, CN, DN, etc.)",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(
        default=True,
        help="Mark as inactive to disable the authorization",
    )

    state = fields.Selection(
        [
            ("valid", "Valid"),
            ("expired", "Expired"),
            ("to_expire", "Expiring Soon"),
        ],
        compute="_compute_state",
        store=True,
    )

    next_number = fields.Integer(
        compute="_compute_next_number",
        help="Next invoice number to use",
    )

    used_numbers = fields.Integer(
        compute="_compute_used_numbers",
        help="Number of numbers already used",
    )

    remaining_numbers = fields.Integer(
        string="Available Numbers",
        compute="_compute_remaining_numbers",
        help="Number of remaining available numbers",
    )

    usage_percentage = fields.Float(
        compute="_compute_usage_percentage",
        help="Percentage of numbers used out of total authorized",
    )

    _unique_timbrado = models.Constraint(
        "unique(name, establishment, expedition_point, series, "
        "l10n_latam_document_type_id, company_id)",
        "The combination of authorization/establishment/expedition point/"
        "series/document type must be unique.",
    )

    @api.depends("date_from", "date_to")
    def _compute_state(self):
        """Compute authorization state based on dates"""
        today = date.today()
        for record in self:
            if not record.date_from or not record.date_to:
                record.state = "valid"
                continue

            if record.date_to < today:
                record.state = "expired"
            elif (record.date_to - today).days <= 30:
                record.state = "to_expire"
            else:
                record.state = "valid"

    @api.depends()
    def _compute_next_number(self):
        """Compute the next available number"""
        for record in self:
            last_invoice = self.env["account.move"].search(
                [
                    ("l10n_py_authorization_id", "=", record.id),
                    ("move_type", "in", ["out_invoice", "out_refund"]),
                ],
                order="l10n_py_invoice_number desc",
                limit=1,
            )

            if last_invoice and last_invoice.l10n_py_invoice_number:
                record.next_number = last_invoice.l10n_py_invoice_number + 1
            else:
                record.next_number = record.invoice_number_from

    @api.depends()
    def _compute_used_numbers(self):
        """Compute how many numbers have been used"""
        for record in self:
            count = self.env["account.move"].search_count(
                [
                    ("l10n_py_authorization_id", "=", record.id),
                    ("move_type", "in", ["out_invoice", "out_refund"]),
                ]
            )
            record.used_numbers = count

    @api.depends("used_numbers", "invoice_number_from", "invoice_number_to")
    def _compute_remaining_numbers(self):
        """Compute how many numbers are still available"""
        for record in self:
            total = record.invoice_number_to - record.invoice_number_from + 1
            record.remaining_numbers = total - record.used_numbers

    @api.depends("used_numbers", "invoice_number_from", "invoice_number_to")
    def _compute_usage_percentage(self):
        """Compute the usage percentage of the number range"""
        for record in self:
            total = record.invoice_number_to - record.invoice_number_from + 1
            if total > 0:
                record.usage_percentage = (record.used_numbers / total) * 100
            else:
                record.usage_percentage = 0.0

    @api.constrains("name")
    def _check_timbrado_format(self):
        """Validate authorization number format"""
        for record in self:
            if not record.name.isdigit() or len(record.name) != 8:
                raise ValidationError(
                    self.env._(
                        "The authorization number must contain exactly "
                        "8 numeric digits."
                    )
                )

    @api.constrains("establishment", "expedition_point")
    def _check_codes_format(self):
        """Validate establishment and expedition point format"""
        for record in self:
            if not record.establishment.isdigit() or len(record.establishment) != 3:
                raise ValidationError(
                    self.env._("The establishment code must contain exactly 3 digits.")
                )
            if (
                not record.expedition_point.isdigit()
                or len(record.expedition_point) != 3
            ):
                raise ValidationError(
                    self.env._(
                        "The expedition point code must contain exactly 3 digits."
                    )
                )

    @api.constrains("invoice_number_from", "invoice_number_to")
    def _check_invoice_range(self):
        """Validate that the number range is valid"""
        for record in self:
            if record.invoice_number_from <= 0:
                raise ValidationError(
                    self.env._("The starting number must be greater than zero.")
                )
            if record.invoice_number_to <= record.invoice_number_from:
                raise ValidationError(
                    self.env._(
                        "The ending number must be greater than the starting number."
                    )
                )
            if record.invoice_number_to > MAX_INVOICE_NUMBER:
                raise ValidationError(
                    self.env._(
                        "The ending number cannot exceed %(max)s.",
                        max=MAX_INVOICE_NUMBER,
                    )
                )

    @api.constrains("series")
    def _check_series_format(self):
        """Validate that series is exactly 2 uppercase letters (AA-ZZ)"""
        for record in self:
            if record.series and not re.match(r"^[A-Z]{2}$", record.series):
                raise ValidationError(
                    self.env._(
                        "The series must be exactly 2 uppercase letters "
                        "(e.g.: AA, AB, ZZ)."
                    )
                )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        """Validate that dates are consistent"""
        for record in self:
            if record.date_to < record.date_from:
                raise ValidationError(
                    self.env._("The end date must be after the start date.")
                )

    def _compute_display_name(self):
        """Authorization display format"""
        for record in self:
            doc_type_name = (
                record.l10n_latam_document_type_id.name
                if record.l10n_latam_document_type_id
                else ""
            )
            name = (
                f"Authorization {record.name} "
                f"({record.establishment}-{record.expedition_point})"
            )
            if record.series and record.series != "AA":
                name = f"{name} Series {record.series}"
            if doc_type_name:
                name = f"{name} [{doc_type_name}]"
            record.display_name = name

    def check_validity(self):
        """Verify if the authorization is valid on the current date"""
        self.ensure_one()
        today = date.today()

        if not self.active:
            raise ValidationError(self.env._("The authorization is inactive."))

        if today < self.date_from:
            raise ValidationError(self.env._("The authorization is not yet effective."))

        if today > self.date_to:
            raise ValidationError(self.env._("The authorization has expired."))

        return True

    def check_number_available(self, number, exclude_move_id=False):
        """Verify if a number is available in this authorization"""
        self.ensure_one()

        if number < self.invoice_number_from or number > self.invoice_number_to:
            raise ValidationError(
                self.env._(
                    "Number %(number)s is outside the authorized range "
                    "(%(from_)s - %(to)s.",
                    number=number,
                    from_=self.invoice_number_from,
                    to=self.invoice_number_to,
                )
            )

        # Check if the number has already been used
        domain = [
            ("l10n_py_authorization_id", "=", self.id),
            ("l10n_py_invoice_number", "=", number),
        ]
        if exclude_move_id:
            domain.append(("id", "!=", exclude_move_id))

        existing = self.env["account.move"].search(domain)

        if existing:
            raise ValidationError(
                self.env._(
                    "Number %(number)s has already been used in invoice "
                    "%(invoice_name)s.",
                    number=number,
                    invoice_name=existing[0].name,
                )
            )

        return True
