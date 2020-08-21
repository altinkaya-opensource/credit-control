# Copyright 2020 Tecnativa - Jairo Llopis
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # Update mail.template records for credit.control.communication
    communication_model = env.ref(
        "account_credit_control.model_credit_control_communication"
    )
    replacements = (
        ("object.contact_address", "object.contact_address_id"),
        ("object.current_policy_level", "object.policy_level_id"),
        ("object.get_contact_address()", "object.contact_address_id"),
    )
    for from_, to in replacements:
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE mail_template SET
                subject = REPLACE(subject, %(from)s, %(to)s),
                body_html = REPLACE(body_html, %(from)s, %(to)s)
            WHERE model_id = %(model_id)s
            """,
            {"from": from_, "to": to, "model_id": communication_model.id},
        )
