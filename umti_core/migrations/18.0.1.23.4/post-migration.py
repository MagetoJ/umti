from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    votehead = env.ref(
        'umti_core.admission_structure_votehead', raise_if_not_found=False)
    if votehead and not votehead.paid_once:
        votehead.paid_once = True
