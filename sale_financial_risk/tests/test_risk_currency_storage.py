# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from pathlib import Path
from runpy import run_path
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRiskCurrencyStorage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.try_currency = cls.env.ref("base.TRY")
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        (cls.try_currency | cls.usd | cls.eur).active = True
        cls.company = cls.env["res.company"].create(
            {"name": "Risk currency test", "currency_id": cls.try_currency.id}
        )
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        for currency, rate in [
            (cls.try_currency, 1),
            (cls.usd, 0.02),
            (cls.eur, 1 / 60),
        ]:
            cls.env["res.currency.rate"].create(
                {
                    "currency_id": currency.id,
                    "company_id": cls.company.id,
                    "name": fields.Date.today(),
                    "rate": rate,
                }
            )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "USD risk customer",
                "credit_currency": "manual",
                "manual_credit_currency_id": cls.usd.id,
                "credit_limit": 10000,
                "risk_sale_order_include": True,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Risk test service",
                "type": "service",
                "invoice_policy": "order",
                "taxes_id": [Command.clear()],
            }
        )

    def _order(self, amount, currency=None):
        currency = currency or self.usd
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Risk test prices",
                "currency_id": currency.id,
                "company_id": self.company.id,
            }
        )
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "pricelist_id": pricelist.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_uom_qty": 1,
                            "product_uom": self.product.uom_id.id,
                            "price_unit": amount,
                            "tax_id": [Command.clear()],
                        }
                    )
                ],
            }
        )

    def test_usd_order_uses_company_currency_storage(self):
        order = self._order(8000)
        order.action_confirm()
        self.assertAlmostEqual(order.order_line.risk_amount, 400000)
        self.assertAlmostEqual(self.partner.risk_sale_order, 8000)
        self.assertAlmostEqual(self.partner.risk_remaining_value, 2000)

    def test_third_currency_order_and_risk_currency_change(self):
        order = self._order(100, self.eur)
        order.action_confirm()
        self.assertAlmostEqual(order.order_line.risk_amount, 6000)
        self.assertAlmostEqual(self.partner.risk_sale_order, 120)
        self.partner.manual_credit_currency_id = self.eur
        self.env.invalidate_all()
        self.assertAlmostEqual(self.partner.risk_sale_order, 100)
        self.assertAlmostEqual(order.order_line.risk_amount, 6000)

    def test_second_order_accounts_for_existing_usd_exposure(self):
        self._order(8000).action_confirm()
        result = self._order(3000).action_confirm()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["res_model"], "partner.risk.exceeded.wiz")

    def test_upgrade_refreshes_nonzero_amounts_and_keeps_zero_rows(self):
        order = self._order(100)
        order.action_confirm()
        zero = self._order(50)
        zero.action_confirm()
        lines = order.order_line | zero.order_line
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE sale_order_line SET risk_amount = CASE WHEN id = %s "
            "THEN 100 ELSE 0 END WHERE id IN %s",
            [order.order_line.id, tuple(lines.ids)],
        )
        lines.invalidate_recordset()
        migration = run_path(
            str(Path(__file__).parents[1] / "migrations/16.0.1.1.5/post-migrate.py")
        )["migrate"]
        original_search = type(lines).search
        visited = []

        def search_test_lines(records, domain, **kwargs):
            found = original_search(
                records, domain + [("id", "in", lines.ids)], **kwargs
            )
            visited.extend(found.ids)
            return found

        with patch.object(type(lines), "search", search_test_lines):
            migration(self.env.cr, "16.0.1.1.4")
            migration(self.env.cr, "16.0.1.1.4")
        self.assertEqual(visited, order.order_line.ids * 2)
        self.assertAlmostEqual(order.order_line.risk_amount, 5000)
        self.assertEqual(zero.order_line.risk_amount, 0)
