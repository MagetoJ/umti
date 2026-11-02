from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Put the contracts of already-approved trainers in force.

    Approving a trainer creates the ``hr.contract`` but earlier versions left
    it in *New*; only new approvals went through ``_run_contract``.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "umti.trainer.allocation" not in env or "hr.contract" not in env:
        return
    allocations = env["umti.trainer.allocation"].search([
        ("state", "=", "approved"),
        ("contract_id", "!=", False),
    ])
    for allocation in allocations:
        allocation._run_contract(allocation.contract_id)
