from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .score_utils import percentage, weighted_score

LOCKED_FIELDS = {'marks', 'absent', 'marked', 'remarks', 'student_id', 'assessment_id'}


class UmtiAssessmentMark(models.Model):
    _name = 'umti.assessment.mark'
    _description = 'Assessment Mark'
    _inherit = ['mail.thread']
    _order = 'assessment_id, student_id'

    assessment_id = fields.Many2one(
        'umti.assessment', required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one(
        'school.student', string='Student', required=True, ondelete='restrict', index=True)
    marks = fields.Float()
    absent = fields.Boolean()
    marked = fields.Boolean()
    remarks = fields.Char()
    state = fields.Selection([
        ('draft', 'Draft'), ('verified', 'Verified'), ('published', 'Published'),
    ], default='draft', required=True, copy=False, tracking=True)

    max_marks = fields.Float(related='assessment_id.max_marks')
    pass_marks = fields.Float(related='assessment_id.pass_marks')
    assessment_state = fields.Selection(related='assessment_id.state', string='Assessment Status')
    course_id = fields.Many2one(related='assessment_id.course_id', store=True)
    unit_id = fields.Many2one(related='assessment_id.unit_id', store=True)
    semester_id = fields.Many2one(related='assessment_id.semester_id', store=True)
    academic_year_id = fields.Many2one(related='assessment_id.academic_year_id', store=True)
    company_id = fields.Many2one(related='assessment_id.company_id', store=True)

    percentage = fields.Float(compute='_compute_scores', store=True)
    weighted_score = fields.Float(
        compute='_compute_weighted_score',
        help="Points this mark contributes to the final unit mark. Zero for "
             "types that do not count (Quiz, Mid-Term, ...).")
    grade = fields.Char(compute='_compute_scores', store=True)
    result = fields.Selection([
        ('pass', 'Pass'), ('fail', 'Fail'), ('absent', 'Absent'),
    ], compute='_compute_scores', store=True)

    _sql_constraints = [
        ('assessment_student_uniq', 'unique(assessment_id, student_id)',
         'A student can only have one line per assessment.'),
    ]

    @api.onchange('marks')
    def _onchange_marks(self):
        for rec in self:
            if rec.marks is not None and rec.marks > 0:
                rec.marked = True
                rec.absent = False

    @api.onchange('absent')
    def _onchange_absent(self):
        for rec in self:
            if rec.absent:
                rec.marked = False
                rec.marks = 0.0

    @api.depends('marks', 'absent', 'marked', 'assessment_id.max_marks',
                 'assessment_id.pass_marks')
    def _compute_scores(self):
        for rec in self:
            a = rec.assessment_id
            scale = self.env['umti.grade.scale']._get_default(rec.company_id or a.company_id)
            rec.percentage = 0.0
            rec.grade = rec.result = False
            if rec.absent:
                rec.result = 'absent'
            elif rec.marked and a.max_marks:
                rec.percentage = percentage(rec.marks, a.max_marks)
                rec.grade = scale.grade_for(rec.percentage) if scale else False
                rec.result = 'pass' if rec.marks >= a.pass_marks else 'fail'

    @api.depends('percentage', 'assessment_id.effective_weight')
    def _compute_weighted_score(self):
        for rec in self:
            rec.weighted_score = weighted_score(
                rec.percentage, rec.assessment_id.effective_weight)

    @api.constrains('marks', 'assessment_id')
    def _check_marks(self):
        for rec in self:
            if rec.marks < 0 or rec.marks > rec.assessment_id.max_marks:
                raise ValidationError(_(
                    "Marks must be between 0 and %s.", rec.assessment_id.max_marks))

    def _result_keys(self):
        return {(m.student_id.id, m.unit_id.id, m.semester_id.id, m.academic_year_id.id)
                for m in self}

    def _consolidate(self):
        self.env['umti.unit.result']._refresh(self._result_keys())

    # ----------------------------------------------------------------- ORM
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('marks') and 'marked' not in vals:
                vals['marked'] = True
                vals['absent'] = False
        records = super().create(vals_list)
        if not self.env.context.get('umti_migration') and any(
                r.assessment_id.state == 'cancelled' for r in records):
            raise UserError(_("Marks cannot be added to a cancelled assessment."))
        return records

    def write(self, vals):
        if LOCKED_FIELDS & set(vals):
            for rec in self:
                if rec.state != 'draft':
                    raise UserError(_(
                        "The mark of %s is %s and read-only. Reset it to draft first.",
                        rec.student_id.name, rec.state))
                if rec.assessment_id.state == 'cancelled':
                    raise UserError(_("The assessment is cancelled; its marks are locked."))
            if 'marks' in vals and 'marked' not in vals:
                vals = dict(vals, marked=True, absent=False)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_published(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_("Only draft marks can be deleted."))

    # ------------------------------------------------------------- actions
    def action_verify(self):
        self.assessment_id._check_manager()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft marks can be verified."))
            if rec.assessment_id.state != 'closed':
                raise UserError(_("The assessment must be Completed before marks are verified."))
            if not (rec.marked or rec.absent):
                raise UserError(_("%s has no mark and is not absent.", rec.student_id.name))
        self.write({'state': 'verified'})

    def action_publish(self):
        self.assessment_id._check_manager()
        if any(rec.state != 'verified' for rec in self):
            raise UserError(_("Only verified marks can be published."))
        super(UmtiAssessmentMark, self).write({'state': 'published'})
        self._consolidate()

    def action_reset_draft(self):
        self.assessment_id._check_manager()
        was_published = self.filtered(lambda r: r.state == 'published')
        super(UmtiAssessmentMark, self).write({'state': 'draft'})
        was_published._consolidate()