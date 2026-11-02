from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Trainers of existing class schedules must be able to see their
    students (record rules use student.current_trainer_ids)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['umti.class.schedule'].search([])._refresh_student_trainers()
    env.flush_all()
