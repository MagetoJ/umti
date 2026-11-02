from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill trainer allocation.employee_id from the removed trainer_id.

    The new employee_id is required, so the column must be populated before
    the ORM adds the NOT NULL constraint during the module update.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        ALTER TABLE umti_trainer_allocation
        ADD COLUMN IF NOT EXISTS employee_id integer
    """)
    cr.execute("""
        SELECT id, trainer_id, company_id
          FROM umti_trainer_allocation
         WHERE trainer_id IS NOT NULL
    """)
    rows = cr.fetchall()
    Employee = env['hr.employee'].with_context(active_test=False)
    for allocation_id, user_id, company_id in rows:
        employee = Employee.search([('user_id', '=', user_id)], limit=1)
        if not employee:
            user = env['res.users'].browse(user_id)
            employee = Employee.create({
                'name': user.name or user.login,
                'user_id': user.id,
                'company_id': company_id or user.company_id.id,
                'work_email': user.email or False,
            })
        cr.execute(
            "UPDATE umti_trainer_allocation SET employee_id = %s "
            "WHERE id = %s",
            (employee.id, allocation_id))
