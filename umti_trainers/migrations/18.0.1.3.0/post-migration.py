from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Create portal users and contracts for existing allocations, and point
    the (noupdate) trainer record rule at the employee's user."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    rule = env.ref('umti_trainers.rule_trainer_allocation_trainer', False)
    if rule:
        rule.write({
            'domain_force': "[('employee_id.user_id', '=', user.id)]",
        })

    allocations = env['umti.trainer.allocation'].search([])
    allocations._sync_trainer()
    env.flush_all()
