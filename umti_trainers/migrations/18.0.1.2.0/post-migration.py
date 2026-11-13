from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Excused absences stop counting against attendance, and trainer
    visibility is rebuilt now that unit_enrollment_ids is a real One2many."""
    cr.execute(
        "UPDATE umti_attendance_status SET counts_in_rate = false WHERE code = 'excused'")

    # Leftover relation table created by the old (wrong) Many2many definition.
    cr.execute("SELECT to_regclass('student_id')")
    if cr.fetchone()[0]:
        cr.execute("SELECT COUNT(*) FROM student_id")
        if not cr.fetchone()[0]:
            cr.execute("DROP TABLE student_id")

    env = api.Environment(cr, SUPERUSER_ID, {})
    Student = env['school.student'].with_context(active_test=False)
    students = Student.search([])
    env.add_to_compute(Student._fields['current_trainer_ids'], students)
    Student.flush_model(['current_trainer_ids'])
