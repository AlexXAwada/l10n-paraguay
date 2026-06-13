from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_py")
class TestGeographicData(TransactionCase):
    """Tests for Paraguay geographic data"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_py = cls.env.ref("base.py")

    def test_departments_loaded(self):
        """17 PY departments must be loaded"""
        departments = self.env["res.country.state"].search(
            [("country_id", "=", self.country_py.id)]
        )
        self.assertGreaterEqual(
            len(departments), 17, "Must have at least 17 departments"
        )

    def test_department_set_codes(self):
        """Departments must have SET codes"""
        departments = self.env["res.country.state"].search(
            [
                ("country_id", "=", self.country_py.id),
                ("l10n_py_code", "!=", False),
                ("l10n_py_code", "!=", 0),
            ]
        )
        self.assertGreater(
            len(departments), 0, "At least one department must have SET code"
        )

    def test_cities_loaded(self):
        """PY cities must be loaded"""
        cities = self.env["res.city"].search([("country_id", "=", self.country_py.id)])
        self.assertGreater(len(cities), 0, "Must have cities loaded")

    def test_neighborhoods_loaded(self):
        """Neighborhoods must be loaded"""
        neighborhoods = self.env["l10n_py.neighborhood"].search([])
        self.assertGreater(len(neighborhoods), 0, "Must have neighborhoods loaded")
