from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Seed the trainer particulars, then create portal users/contracts and
    refresh the employees for allocations that predate this change.

    Everything goes through the ORM: res_users has no name/email columns in
    18.0 (they live on the partner) and hr.employee storage has moved around,
    so raw SQL against those tables is version-fragile.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    # trainer_id was removed in 18.0.1.3.0 but its column stays behind.
    cr.execute("""
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'umti_trainer_allocation'
    """)
    columns = {row[0] for row in cr.fetchall()}
    legacy_users = {}
    if 'trainer_id' in columns:
        cr.execute("""
            SELECT id, trainer_id
              FROM umti_trainer_allocation
             WHERE trainer_id IS NOT NULL
        """)
        legacy_users = dict(cr.fetchall())

    Allocation = env['umti.trainer.allocation']
    for rec in Allocation.search([]):
        if rec.trainer_name:
            continue
        vals = {}
        if rec.employee_id:
            vals = {
                'trainer_name': rec.employee_id.name,
                'trainer_email': rec.employee_id.work_email,
            }
        elif legacy_users.get(rec.id):
            user = env['res.users'].browse(legacy_users[rec.id])
            vals = {
                'trainer_name': user.name,
                'trainer_email': user.email,
            }
        if vals.get('trainer_name'):
            rec.with_context(umti_skip_trainer_sync=True).write(vals)

    Allocation.search([])._sync_trainer()
    env.flush_all()
