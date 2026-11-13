from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SchoolStudentInherit(models.Model):
    _inherit = 'school.student'

    course_level = fields.Selection([
    ('yr_one', 'Year 1'),
    ('yr_two', 'Year 2'),
    ('yr_three', 'Year 3'),
    ('yr_four', 'Year 4'),
    ('yr_five', 'Year 5'),
    ('yr_six', 'Year 6'),],
    default='yr_one', string='Level', tracking=True)
    
    
    enrollment_ids = fields.One2many(
        'umti.student.unit.enrollment', 'student_id',
        string='Unit Enrollments')

    enrollment_count = fields.Integer(
        string='Enrollment Count', compute='_compute_enrollment_count')

    def action_view_attendance_analysis(self):
        """Open the student's attendance as a chart (graph first, list second).

        Graph/pivot views are main views only: they cannot be embedded in a
        form field, hence this dedicated action.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance Chart - %s', self.name),
            'res_model': 'umti.attendance.line',
            'view_mode': 'graph,list,form',
            'views': [
                (self.env.ref(
                    'umti_trainers.umti_attendance_line_view_graph').id,
                 'graph'),
                (False, 'list'),
                (False, 'form'),
            ],
            'domain': [('student_id', '=', self.id)],
            'context': {'create': False},
        }

    current_trainer_ids = fields.Many2many(
        'res.users', 'student_current_trainer_rel',
        'student_id', 'user_id',
        string='Current Trainers', compute='_compute_current_trainers', store=True)

    @api.depends('enrollment_ids')
    def _compute_enrollment_count(self):
        for rec in self:
            rec.enrollment_count = len(rec.enrollment_ids)

    #TODO: All this Selections to Many2one. Probably something we can do about that
    def _auto_fill_enrollment(self):
        """Enroll the students in the units of their running semester.

        Called per student when their semester starts, and by the trainers
        cron in batches. Batched on purpose: one query for the existing
        enrollments and one create for the whole recordset, so opening a term
        for a large student base never becomes a query-per-student loop.
        """
        students = self.filtered("course_id")
        if not students:
            return
        Enrollment = self.env["umti.student.unit.enrollment"].sudo()
        Unit = self.env["umti.course.units"]

        # 1. Running semester and term, per student.
        plans = {}
        term_ids = set()
        for student in students:
            # The newest active semester is the one being attended now; an
            # older one may still be open as a carry-over after a failed
            # term, and must not receive this term's enrolments.
            semester = student.semester_ids.filtered(
                lambda s: s.state == "active").sorted(
                    'sequence', reverse=True)[:1]
            if not semester:
                continue
            term = semester.academic_term_id or student._get_current_term()
            if not term:
                continue
            plans[student.id] = (student, semester, term)
            term_ids.add(term.id)
        if not plans:
            return

        # 2. What already exists for these students and terms (one query).
        existing = {}
        for enrollment in Enrollment.search([
            ("student_id", "in", list(plans)),
            ("academic_term_id", "in", list(term_ids)),
        ]):
            key = (enrollment.student_id.id, enrollment.academic_term_id.id)
            existing[key] = existing.get(key, Unit) | enrollment.unit_id

        # 3. One create for everything missing.
        vals_list = []
        for student_id in plans:
            student, semester, term = plans[student_id]
            units = student._units_for_semester(semester)
            have = existing.get((student.id, term.id), Unit)
            vals_list.extend([{
                "student_id": student.id,
                "course_id": student.course_id.id,
                "unit_id": unit.id,
                "academic_term_id": term.id,
                "state": "enrolled",
            } for unit in units - have])
        if vals_list:
            Enrollment.create(vals_list)

    def _units_for_semester(self, semester):
        """Units placed in the given study period of the student's course.

        The course's unit plan (``umti.course.unit.line``) is authoritative:
        it lets a shared unit sit in different years or periods for different
        courses. Courses that predate the unit plan fall back to the legacy
        ``unit_level`` / ``unit_semester`` fields on the unit.
        """
        self.ensure_one()
        Unit = self.env['umti.course.units']
        course = self.course_id
        year_num = semester.course_year or 1

        pattern = course._get_term_pattern() if course else False
        main_lines = pattern._main_lines() if pattern else False
        period_sequence = (semester.academic_term_id.sequence
                           if semester.academic_term_id else False)
        if not period_sequence and main_lines:
            index = (max(semester.sequence or 1, 1) - 1) % len(main_lines)
            period_sequence = main_lines[index].sequence

        lines = course.unit_line_ids.filtered(
            lambda line: line.active and line.unit_id.active
            and line.unit_id in course.unit_ids)
        if lines:
            same_year = lines.filtered(
                lambda line: line.course_year == year_num) or lines
            if period_sequence:
                matched = same_year.filtered(
                    lambda line: line.period_sequence == period_sequence)
                same_year = matched or same_year
            return same_year.mapped('unit_id')

        units = course.unit_ids.filtered('active')
        # 'other' is a catch-all, not a year: keep the year keys only.
        level_keys = [key for key, _label
                      in Unit._fields['unit_level'].selection
                      if key != 'other']
        if 0 < year_num <= len(level_keys):
            level_key = level_keys[year_num - 1]
        elif self.course_level in level_keys:
            level_key = self.course_level
        else:
            level_key = False
        if level_key:
            units = units.filtered(lambda u: u.unit_level == level_key)
        sem_key = 'sem_%d' % (((semester.sequence or 1) - 1) % 4 + 1)
        return units.filtered(lambda u: u.unit_semester == sem_key) or units

    # ------------------------------------------------------------------
    # Progression: units per semester state (completed / current / upcoming)
    # ------------------------------------------------------------------
    completed_unit_ids = fields.Many2many(
        'umti.course.units', string='Completed Units',
        compute='_compute_unit_progression')
    current_unit_ids = fields.Many2many(
        'umti.course.units', string='Current Units',
        compute='_compute_unit_progression')
    upcoming_unit_ids = fields.Many2many(
        'umti.course.units', string='Upcoming Units',
        compute='_compute_unit_progression')

    @api.depends('course_id', 'course_id.unit_ids',
                 'course_id.unit_line_ids', 'course_level',
                 'semester_ids.state', 'semester_ids.sequence',
                 'semester_ids.course_year',
                 'semester_ids.academic_term_id')
    def _compute_unit_progression(self):
        Unit = self.env['umti.course.units']
        for student in self:
            completed = current = upcoming = Unit
            for semester in student.semester_ids.sorted('sequence'):
                units = student._units_for_semester(semester)
                if semester.state == 'complete':
                    completed |= units
                elif semester.state == 'active':
                    current |= units
                else:
                    upcoming |= units
            student.completed_unit_ids = completed
            student.current_unit_ids = current
            student.upcoming_unit_ids = upcoming


    @api.depends('enrollment_ids.state', 'enrollment_ids.unit_id',
                 'enrollment_ids.academic_term_id', 'enrollment_ids.trainer_id')
    def _compute_current_trainers(self):
        Allocation = self.env['umti.trainer.allocation']
        for student in self:
            active_enrollments = student.enrollment_ids.filtered(
                lambda e: e.state == 'enrolled')
            if not active_enrollments:
                student.current_trainer_ids = False
                continue
            # Trainers explicitly assigned to the enrollment by the
            # department win over the allocation fallback.
            trainers = active_enrollments.mapped('trainer_id.user_id')
            if not trainers:
                allocations = Allocation.search([
                    ('unit_ids', 'in', active_enrollments.unit_id.ids),
                    ('active', '=', True),
                    ('state', '=', 'approved'),
                ])
                trainers = allocations.mapped('employee_id.user_id')
            student.current_trainer_ids = trainers

    def action_enroll_course_units(self):
        """Button wrapper: enroll now and tell the user what happened."""
        term = self._get_current_term()
        if not term:
            raise UserError(_(
                "No open semester found. Create or start a term first."))
        created = self.action_auto_enroll_units(term=term)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Unit Enrollment'),
                'message': _('%(n)d unit enrollment(s) created for %(term)s.',
                             n=len(created), term=term.name),
                'type': 'success' if created else 'warning',
                'sticky': False,
            },
        }

    def _get_baseline_units(self):
        """Units a student takes first: Year 1, Semester 1 of the course.

        Falls back to every unit of the course when the units carry no
        usable level/semester so a student is never left with no units.
        """
        self.ensure_one()
        units = self.course_id.unit_ids.filtered('active')
        first = units.filtered(
            lambda u: u.unit_level == 'yr_one' and u.unit_semester == 'sem_1')
        return first or units

    def action_auto_enroll_units(self, term=None):
        """Enroll the student in the units of their course for the term.

        A student with no earlier enrollments gets the first-semester units;
        otherwise the level filter used by the transition wizard applies.
        Returns the enrollments created.
        """
        Enrollment = self.env['umti.student.unit.enrollment']
        created = Enrollment
        for student in self:
            if not student.course_id:
                continue
            target_term = term or student._get_current_term()
            if not target_term:
                continue
            has_history = Enrollment.sudo().search_count(
                [('student_id', '=', student.id)])
            if has_history:
                units = student.course_id.unit_ids.filtered('active')
                if student.level_id:
                    year_key = {
                        'umti_core.course_level_certificate': 'yr_one',
                    }
                    for xmlid, key in year_key.items():
                        level = self.env.ref(xmlid, False)
                        if level and student.level_id == level:
                            units = units.filtered(lambda u: u.unit_level == key)
            else:
                units = student._get_baseline_units()
            existing = Enrollment.sudo().search([
                ('student_id', '=', student.id),
                ('academic_term_id', '=', target_term.id),
            ]).mapped('unit_id')
            vals_list = [{
                'student_id': student.id,
                'course_id': student.course_id.id,
                'unit_id': unit.id,
                'academic_term_id': target_term.id,
                'state': 'enrolled',
            } for unit in units - existing]
            if vals_list:
                created |= Enrollment.sudo().create(vals_list)
        return created

    def _get_current_term(self):
        """Best term for this student's course: running, open, then next.

        Terms are course-owned now, so the fallback must never pick another
        course's running term. Shared legacy terms (no course) still match.
        """
        Term = self.env['umti.academic.term']
        today = fields.Date.context_today(self)
        course_ids = self.mapped('course_id').ids
        course_domain = (
            [('course_id', 'in', course_ids + [False])] if course_ids else [])
        for domain in (
            [('term_start_date', '<=', today), ('term_end_date', '>=', today),
             ('status', '=', 'in_progress')],
            [('term_start_date', '<=', today), ('term_end_date', '>=', today),
             ('status', '!=', 'ended')],
        ):
            term = Term.search(
                course_domain + domain,
                order='term_start_date desc', limit=1)
            if term:
                return term
        upcoming = Term.search(
            course_domain + [
                ('term_start_date', '>', today), ('status', '!=', 'ended'),
            ], order='term_start_date asc', limit=1)
        if upcoming:
            return upcoming
        # Dates may not have been kept up to date: use the latest open term.
        return Term.search(
            course_domain + [('status', '!=', 'ended')],
            order='term_start_date desc', limit=1)

    def action_view_enrollments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Unit Enrollments'),
            'res_model': 'umti.student.unit.enrollment',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
