from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError

from .assessment_types import CORE_TYPES, DEFAULT_CORE_WEIGHTS
from .score_utils import percentage

MANAGER_GROUPS = ('umti_exams.group_umti_exams_manager', 'base.group_system')
LEARNING_OUTCOME_SCORE_FIELDS = (
    'lo1_t', 'lo1_p', 'lo2_t', 'lo2_p',
    'lo3_t', 'lo3_p', 'lo4_t', 'lo4_p',
)

class UMTIUnitResult(models.Model):
    _name = 'umti.unit.result'
    _description = 'Trainee Unit Examination Result'
    _rec_name = 'student_id'

    student_id = fields.Many2one('school.student', string='Trainee Name', required=True, ondelete='cascade')
    adm_no = fields.Char(related='student_id.admission_no', string='ADM NO', store=True, readonly=True)
    
    course_id = fields.Many2one(related='student_id.course_id', store=True, readonly=True)
    unit_id = fields.Many2one('umti.course.units', string='Unit of Competence', required=True)
    semester_id = fields.Many2one(
        'umti.academic.term', string='Semester / Term', required=True, index=True)
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester',
        related='semester_id', store=True, readonly=False)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year',
        related='semester_id.academic_year_id', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    # --- Consolidated result ---
    weight_total = fields.Float(string='Total Weight (%)', readonly=True)
    pending_count = fields.Integer(string='Pending Assessments', readonly=True)
    cat_percent = fields.Float(string='CATs (%)', readonly=True)
    assignment_percent = fields.Float(string='Assignments (%)', readonly=True)
    exam_percent = fields.Float(string='Final Exam (%)', readonly=True)
    final_mark = fields.Float(string='Final Mark', readonly=True)
    grade = fields.Char(readonly=True)
    result = fields.Selection([('pass', 'Pass'), ('fail', 'Fail')], readonly=True)
    is_complete = fields.Boolean(string='Complete', readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('published', 'Published')],
        default='draft', required=True, copy=False)
    exam_record_id = fields.Many2one('umti.exam.record', string='Exam Record', readonly=True, copy=False)

    _sql_constraints = [
        ('student_unit_semester_uniq', 'unique(student_id, unit_id, semester_id)',
         'A trainee can only have one result per unit and semester.'),
    ]

    # --- Learning Outcome 1 ---
    lo1_t_raw = fields.Float(string='LO1-T Raw Mark')
    lo1_t_max = fields.Float(string='LO1-T Max Mark', default=100.0)
    lo1_t = fields.Float(string='LO1-T (%)', compute='_compute_lo_scores', store=True)

    lo1_p_raw = fields.Float(string='LO1-P Raw Mark')
    lo1_p_max = fields.Float(string='LO1-P Max Mark', default=100.0)
    lo1_p = fields.Float(string='LO1-P (%)', compute='_compute_lo_scores', store=True)

    # --- Learning Outcome 2 ---
    lo2_t_raw = fields.Float(string='LO2-T Raw Mark')
    lo2_t_max = fields.Float(string='LO2-T Max Mark', default=100.0)
    lo2_t = fields.Float(string='LO2-T (%)', compute='_compute_lo_scores', store=True)

    lo2_p_raw = fields.Float(string='LO2-P Raw Mark')
    lo2_p_max = fields.Float(string='LO2-P Max Mark', default=100.0)
    lo2_p = fields.Float(string='LO2-P (%)', compute='_compute_lo_scores', store=True)

    # --- Learning Outcome 3 ---
    lo3_t_raw = fields.Float(string='LO3-T Raw Mark')
    lo3_t_max = fields.Float(string='LO3-T Max Mark', default=100.0)
    lo3_t = fields.Float(string='LO3-T (%)', compute='_compute_lo_scores', store=True)

    lo3_p_raw = fields.Float(string='LO3-P Raw Mark')
    lo3_p_max = fields.Float(string='LO3-P Max Mark', default=100.0)
    lo3_p = fields.Float(string='LO3-P (%)', compute='_compute_lo_scores', store=True)

    # --- Learning Outcome 4 ---
    lo4_t_raw = fields.Float(string='LO4-T Raw Mark')
    lo4_t_max = fields.Float(string='LO4-T Max Mark', default=100.0)
    lo4_t = fields.Float(string='LO4-T (%)', compute='_compute_lo_scores', store=True)

    lo4_p_raw = fields.Float(string='LO4-P Raw Mark')
    lo4_p_max = fields.Float(string='LO4-P Max Mark', default=100.0)
    lo4_p = fields.Float(string='LO4-P (%)', compute='_compute_lo_scores', store=True)

    # --- Summary Calculations ---
    final_score = fields.Float(string='Final Score (%)', compute='_compute_final_results', store=True)
    remarks = fields.Selection([
        ('competent', 'Competent'),
        ('not_yet_competent', 'Not Yet Competent')
    ], string='REMARKS', compute='_compute_final_results', store=True)

    @api.depends('lo1_t_raw', 'lo1_t_max', 'lo1_p_raw', 'lo1_p_max',
                 'lo2_t_raw', 'lo2_t_max', 'lo2_p_raw', 'lo2_p_max',
                 'lo3_t_raw', 'lo3_t_max', 'lo3_p_raw', 'lo3_p_max',
                 'lo4_t_raw', 'lo4_t_max', 'lo4_p_raw', 'lo4_p_max')
    def _compute_lo_scores(self):
        for rec in self:
            for field_name in LEARNING_OUTCOME_SCORE_FIELDS:
                raw_mark = getattr(rec, f'{field_name}_raw')
                max_mark = getattr(rec, f'{field_name}_max')
                setattr(rec, field_name, round(percentage(raw_mark, max_mark), 2))

    @api.depends('lo1_t', 'lo1_p', 'lo2_t', 'lo2_p', 'lo3_t', 'lo3_p', 'lo4_t', 'lo4_p')
    def _compute_final_results(self):
        for rec in self:
            scores = [getattr(rec, field_name) for field_name in LEARNING_OUTCOME_SCORE_FIELDS]
            valid_scores = [score for score in scores if score > 0]
            rec.final_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0
            rec.remarks = 'competent' if rec.final_score >= 50.0 else 'not_yet_competent'

    # ------------------------------------------------------------------
    # Consolidation of published assessment marks
    # ------------------------------------------------------------------
    @api.model
    def _refresh(self, keys):
        """Rebuild results for (student, unit, semester, year) tuples."""
        Assessment = self.env['umti.assessment'].sudo()
        Mark = self.env['umti.assessment.mark'].sudo()
        Plan = self.env['umti.assessment.plan']
        Student = self.env['school.student'].sudo()
        Term = self.env['umti.academic.term'].sudo()
        for student_id, unit_id, semester_id, _year_id in set(keys):
            if not (student_id and unit_id and semester_id):
                continue
            student = Student.browse(student_id)
            domain = [
                ('unit_id', '=', unit_id), ('semester_id', '=', semester_id),
                ('state', '!=', 'cancelled')]
            if student.course_id:
                domain.append(('course_id', '=', student.course_id.id))
            assessments = Assessment.search(domain)
            marks = Mark.search([
                ('student_id', '=', student_id), ('assessment_id', 'in', assessments.ids),
                ('state', 'in', ['verified', 'published'])])

            department = student.course_id.department_id or assessments[:1].department_id
            semester = Term.browse(semester_id)
            weights = dict(DEFAULT_CORE_WEIGHTS)
            if department and semester.exists():
                weights = Plan._get_or_create(semester, department).core_weights()

            components = {'cat': 0.0, 'assignment': 0.0, 'final': 0.0}
            lo_vals = {f: 0.0 for f in LEARNING_OUTCOME_SCORE_FIELDS}

            for m in marks:
                a_type = m.assessment_id.assessment_type
                lo_type = m.assessment_id.learning_outcome_type
                
                # Check outcome mapping first
                if lo_type in lo_vals:
                    lo_vals[lo_type] = m.percentage
                elif lo_type == 'cat':
                    components['cat'] = m.percentage
                elif lo_type == 'assignment':
                    components['assignment'] = m.percentage
                elif lo_type == 'final_exam':
                    components['final'] = m.percentage

                # Fallback to standard assessment_type
                if a_type in components and not lo_type:
                    components[a_type] = m.percentage

            final_mark = sum(components[k] * weights.get(k, 0.0) / 100.0 for k in CORE_TYPES)
            published_assessments = marks.filtered(lambda m: m.state == 'published').mapped('assessment_id')
            pending = max(0, len(assessments) - len(published_assessments))
            complete = pending == 0

            vals = {
                'weight_total': sum(weights.values()),
                'pending_count': pending,
                'cat_percent': round(components['cat'], 2),
                'assignment_percent': round(components['assignment'], 2),
                'exam_percent': round(components['final'], 2),
                'final_mark': round(final_mark, 2),
                'is_complete': complete,
                'grade': False,
                'result': False,
            }
            vals.update({k: round(v, 2) for k, v in lo_vals.items()})

            company = assessments[:1].company_id
            if complete:
                scale = self.env['umti.grade.scale']._get_default(company)
                vals['grade'] = scale.grade_for(final_mark) if scale else False
                vals['result'] = 'pass' if (scale.is_pass(final_mark) if scale else final_mark >= 50.0) else 'fail'

            rec = self.search([
                ('student_id', '=', student_id), ('unit_id', '=', unit_id),
                ('semester_id', '=', semester_id)], limit=1)
            if rec:
                if rec.state == 'published':
                    vals['state'] = 'draft'
                rec.write(vals)
            else:
                self.create(dict(
                    vals, student_id=student_id, unit_id=unit_id, semester_id=semester_id,
                    company_id=(company or self.env.company).id))

    def _missing_components(self):
        self.ensure_one()
        labels = {'cat': 'CAT', 'assignment': 'Assignment', 'final': 'Final Exam'}
        domain = [
            ('unit_id', '=', self.unit_id.id), ('semester_id', '=', self.semester_id.id),
            ('state', '!=', 'cancelled'), ('assessment_type', 'in', CORE_TYPES)]
        if self.student_id.course_id:
            domain.append(('course_id', '=', self.student_id.course_id.id))
        assessments = self.env['umti.assessment'].sudo().search(domain)
        published = self.env['umti.assessment.mark'].sudo().search([
            ('student_id', '=', self.student_id.id), ('assessment_id', 'in', assessments.ids),
            ('state', '=', 'published')]).assessment_id
        lines = []
        for kind in CORE_TYPES:
            of_kind = assessments.filtered(lambda a, k=kind: a.assessment_type == k)
            if not of_kind:
                lines.append(_("- %s: no assessment has been created for this unit.", labels[kind]))
                continue
            waiting = of_kind - published
            if waiting:
                lines.append(_(
                    "- %(kind)s: marks not yet published for %(names)s.",
                    kind=labels[kind], names=", ".join(waiting.mapped('name'))))
        return lines or [_("- Refresh the result and try again.")]

    def _check_manager(self):
        if not any(self.env.user.has_group(g) for g in MANAGER_GROUPS):
            raise AccessError(_("Only an exams manager can publish unit results."))

    def action_publish(self):
        self._check_manager()
        ExamRecord = self.env['umti.exam.record'].sudo()
        for rec in self:
            if not rec.is_complete:
                raise UserError(_(
                    "%(name)s cannot be published yet. The final mark needs CAT, "
                    "Assignment and Final Exam results, and these are still missing:"
                    "\n\n%(missing)s",
                    name=rec.display_name, missing="\n".join(rec._missing_components())))
            vals = {
                'student_id': rec.student_id.id,
                'academic_year_id': rec.academic_year_id.id,
                'semester_id': rec.semester_id.id,
                'course_id': rec.course_id.id,
                'unit_id': rec.unit_id.id,
                'marks': rec.final_mark,
                'max_marks': 100.0,
                'exam_date': fields.Date.context_today(rec),
                'company_id': rec.company_id.id,
            }
            record = rec.exam_record_id or ExamRecord.search([
                ('student_id', '=', rec.student_id.id), ('unit_id', '=', rec.unit_id.id),
                ('semester_id', '=', rec.semester_id.id)], limit=1)
            if record:
                record.write(vals)
            else:
                record = ExamRecord.create(vals)
            rec.write({'state': 'published', 'exam_record_id': record.id})
        return True