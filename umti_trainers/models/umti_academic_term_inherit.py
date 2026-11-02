from odoo import models


class UmtiAcademicTermInherit(models.Model):
    """Start the student semesters when a term starts.

    A main semester *is* a semester: billing, results and the student
    ladder all agree on that. When one becomes in progress, every active
    student must be pointed at the semester that just started. That is the
    only place where the calendar and a student's progress are joined.
    """

    _inherit = 'umti.academic.term'

    def write(self, vals):
        # Read the previous state, then write. Terms are generated a whole
        # year at a time, so only a real transition to in progress counts.
        becoming_running = self.filtered(
            lambda term: vals.get('status') == 'in_progress'
            and term.status != 'in_progress')
        res = super().write(vals)
        if becoming_running.filtered(lambda term: not term.parent_term):
            self.env['umti.student.semester'].sudo()._start_pending()
        return res
