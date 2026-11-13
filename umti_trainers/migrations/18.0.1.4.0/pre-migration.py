from odoo import SUPERUSER_ID


def migrate(cr, version):
    """Add the trainer particular columns.

    trainer_name is required, so a placeholder must be written before the ORM
    applies the NOT NULL constraint. The real values are seeded from the
    employee / legacy user by the post-migration, through the ORM (no raw SQL
    against res_users / hr_employee columns, whose storage differs by version).
    """
    if not version:
        return
    cr.execute("""
        ALTER TABLE umti_trainer_allocation
        ADD COLUMN IF NOT EXISTS trainer_name varchar,
        ADD COLUMN IF NOT EXISTS trainer_email varchar,
        ADD COLUMN IF NOT EXISTS trainer_phone varchar
    """)
    cr.execute("""
        UPDATE umti_trainer_allocation
           SET trainer_name = COALESCE(trainer_name, ''),
               trainer_email = COALESCE(trainer_email, ''),
               trainer_phone = COALESCE(trainer_phone, '')
         WHERE trainer_name IS NULL
            OR trainer_email IS NULL
            OR trainer_phone IS NULL
    """)
