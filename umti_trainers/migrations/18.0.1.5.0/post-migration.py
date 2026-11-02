from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Trainers that already got an employee from the previous flow are
    approved by definition; the rest stay in draft."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    allocations = env['umti.trainer.allocation'].search([
        ('employee_id', '!=', False),
    ])
    allocations.with_context(
        umti_skip_trainer_sync=True).write({'state': 'approved'})
    env.flush_all()
