from odoo import _, api, fields, models
from odoo.exceptions import UserError


class UmtiStudentSemesterInherit(models.Model):
    _inherit = 'umti.student.semester'

    def write(self, vals):
        """Starting a semester enrolls the student in its units.

        Batch callers (the term switch, the cron) pass umti_skip_enroll and
        enrol the whole set once instead of once per student.
        """
        res = super().write(vals)
        if (vals.get('state') == 'active'
                and not self.env.context.get('umti_skip_enroll')):
            self.student_id._auto_fill_enrollment()
        return res

    @api.model
    def _running_term(self):
        """The main term that is running now, or today's, or the latest."""
        Term = self.env['umti.academic.term']
        base = [('parent_term', '=', False), ('status', '=', 'in_progress'),
                ('active', '=', True)]
        today = fields.Date.context_today(self)
        term = Term.search(base + [
            ('term_start_date', '<=', today),
            ('term_end_date', '>=', today),
        ], order='term_start_date desc', limit=1)
        return term or Term.search(base, order='term_start_date desc', limit=1)

    @api.model
    def _start_pending(self):
        """Point every active student at the semester that is now running.

        Called when a main term becomes in progress, and by the nightly cron
        as a safety net. Idempotent: a student already on the running term is
        skipped.

        A semester with failed or unfinished results is left open and the
        student is put on hold; the student still advances, because a hold
        only blocks graduation (carry-over units are normal). A semester with
        no results yet is also left open, but without a hold: marks are
        usually published after the next term has started.
        """
        running = self._running_term()
        if not running:
            return self.browse()
        Semester = self.sudo()
        students = self.env['school.student'].sudo().search([
            ('state', '=', 'active'),
            ('semester_ids', '!=', False),
        ])
        advanced = self.env['school.student']
        for student in students:
            semesters = student.semester_ids
            if semesters.filtered(lambda s: s.academic_term_id == running):
                continue
            for semester in semesters.filtered(lambda s: s.state == 'active'):
                state = semester._results_state()
                if state['ok']:
                    semester.write({'state': 'complete'})
                elif state['failed'] or state['incomplete']:
                    if not student.has_hold:
                        student.write({'has_hold': True})
                    semester.message_post(body=_(
                        "%(semester)s was left open because its results are "
                        "failed or unfinished. %(student)s is on hold until "
                        "an administrator resolves it.",
                        semester=semester.name,
                        student=student.display_name))
                # state['missing']: wait for the marks, no hold.
            next_semester = semesters.filtered(
                lambda s: s.state == 'draft').sorted('sequence')[:1]
            if next_semester:
                next_semester.with_context(umti_skip_enroll=True).write({
                    'academic_term_id': running.id,
                    'academic_year_id': running.academic_year_id.id,
                    'state': 'active',
                })
                advanced |= student
        if advanced:
            advanced._auto_fill_enrollment()
        return Semester.search([
            ('academic_term_id', '=', running.id),
            ('state', '=', 'active'),
        ])

    @api.model
    def _cron_advance_semesters(self):
        """Daily: keep enrolments in sync and move students forward."""
        Semester = self.sudo()
        # Running semesters always have their units enrolled.
        Semester.search([('state', '=', 'active')]).student_id._auto_fill_enrollment()
        # Students whose term has already changed are moved onto it.
        self._start_pending()

    def action_assign_unit_trainers(self):
        """Open the unit trainer assignments of this semester so the
        department can set who teaches each unit."""
        self.ensure_one()
        if not self.academic_term_id:
            raise UserError(_(
                "Set an semester on semester %(name)s before assigning "
                "trainers.", name=self.display_name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Unit Trainers - %s', self.display_name),
            'res_model': 'umti.unit.trainer',
            'view_mode': 'list,form',
            'domain': [
                ('unit_id', 'in', self.student_id.course_id.unit_ids.ids),
                ('academic_term_id', '=', self.academic_term_id.id),
            ],
            'context': {
                'default_academic_term_id': self.academic_term_id.id,
                'default_academic_year_id': self.academic_term_id.academic_year_id.id,
            },
        }
