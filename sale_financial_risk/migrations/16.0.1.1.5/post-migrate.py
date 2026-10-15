# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Refresh nonzero stored amounts in their declared company currency."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    last_id = 0
    while True:
        lines = env["sale.order.line"].search(
            [("id", ">", last_id), ("risk_amount", "!=", 0)],
            order="id",
            limit=1000,
        )
        if not lines:
            break
        lines._compute_risk_amount()
        last_id = lines[-1].id
        env.invalidate_all()
