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
    def _running_terms(self):
        """Main terms that are running today, across courses and cohorts."""
        Term = self.env['umti.academic.term']
        today = fields.Date.context_today(self)
        return Term.search([
            ('parent_term', '=', False),
            ('status', '=', 'in_progress'),
            ('active', '=', True),
            ('term_start_date', '<=', today),
            ('term_end_date', '>=', today),
        ], order='course_id, term_start_date')

    @api.model
    def _term_set(self, running):
        """All main terms that form one cohort's sequence."""
        Term = self.env['umti.academic.term']
        domain = [
            ('parent_term', '=', False),
            ('course_id', '=', running.course_id.id),
        ]
        if running.pattern_id:
            domain.append(('pattern_id', '=', running.pattern_id.id))
        if running.intake_id:
            domain.append(('intake_id', '=', running.intake_id.id))
        terms = Term.search(domain, order='term_start_date')
        if running not in terms:
            terms |= running
        return terms.sorted('term_start_date')

    @api.model
    def _student_in_cohort(self, student, running):
        if not running.intake_id:
            return True
        if student.application_id.intake_id == running.intake_id:
            return True
        return any(
            semester.academic_term_id.intake_id == running.intake_id
            for semester in student.semester_ids)

    @api.model
    def _start_pending(self, term=None):
        """Advance the students whose next period has just started.

        Called when a main term becomes in progress, and by the nightly cron
        as a safety net. Idempotent: a student already on the running term is
        skipped. A failed or unfinished semester stays open and puts the
        student on hold, but the student still advances; a semester with no
        results yet is left open without a hold.
        """
        advanced = self.browse()
        for running in (term or self._running_terms()):
            advanced |= self._advance_term(running)
        return advanced

    @api.model
    def _advance_term(self, running):
        Term = self.env['umti.academic.term']
        domain = [
            ('state', '=', 'active'),
            ('semester_ids', '!=', False),
        ]
        if running.course_id:
            domain.append(('course_id', '=', running.course_id.id))
        students = self.env['school.student'].sudo().search(domain)
        sequence = self._term_set(running)
        index = list(sequence).index(running)
        previous = sequence[index - 1] if index else Term
        advanced = self.browse()
        for student in students:
            if not self._student_in_cohort(student, running):
                continue
            semesters = student.semester_ids
            active = semesters.filtered(lambda s: s.state == 'active')
            if active.filtered(lambda s: s.academic_term_id == running):
                continue
            current = active.sorted('sequence', reverse=True)[:1]
            current_term = current.academic_term_id
            if current_term == running:
                continue
            if previous:
                due = current_term == previous
                if not due and not current_term:
                    last_complete = semesters.filtered(
                        lambda s: s.state == 'complete').sorted(
                            'sequence', reverse=True)[:1]
                    due = last_complete.academic_term_id == previous
                if not due:
                    continue
            elif current_term:
                continue

            for semester in active:
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
                advanced |= next_semester
            else:
                # action_mark_complete already activated the next row; it
                # only needs the term that has just started.
                waiting = semesters.filtered(
                    lambda s: s.state == 'active'
                    and not s.academic_term_id).sorted('sequence')[:1]
                if waiting:
                    waiting.with_context(umti_skip_enroll=True).write({
                        'academic_term_id': running.id,
                        'academic_year_id': running.academic_year_id.id,
                    })
                    advanced |= waiting
        if advanced:
            advanced.student_id._auto_fill_enrollment()
        return advanced

    @api.model
    def _cron_advance_semesters(self):
        """Daily: keep enrolments in sync and move students forward."""
        Semester = self.sudo()
        Semester.search([('state', '=', 'active')]).student_id._auto_fill_enrollment()
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
