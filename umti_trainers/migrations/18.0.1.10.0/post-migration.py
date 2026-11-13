from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Staff the units of trainers approved before this version.

    Approving an allocation now creates the ``umti.unit.trainer`` rows for the
    running term; allocations approved earlier never did, which left the Unit
    Trainers list, the enrollment trainer and the timetable without a trainer.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "umti.unit.trainer" not in env:
        return
    allocations = env["umti.trainer.allocation"].search([
        ("state", "=", "approved"),
        ("employee_id", "!=", False),
    ])
    allocations._assign_units_for_running_term()
