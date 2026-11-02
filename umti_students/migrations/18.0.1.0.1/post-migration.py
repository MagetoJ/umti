from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute("""
        UPDATE school_student
        SET blood_group = lower(blood_group)
        WHERE blood_group IS NOT NULL
          AND blood_group <> lower(blood_group)
    """)
