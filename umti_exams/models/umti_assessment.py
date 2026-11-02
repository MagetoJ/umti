from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .assessment_types import ASSESSMENT_TYPES, CORE_TYPES, DEFAULT_CORE_WEIGHTS

MANAGER_GROUPS = ('umti_exams.group_umti_exams_manager', 'base.group_system')


class UmtiAssessment(models.Model):
    _name = 'umti.assessment'
    _description = 'Course Assessment & Exam Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Title', required=True, tracking=True)
    code = fields.Char(string='Exam Code', required=True, copy=False, default='New', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    course_id = fields.Many2one('umti.course', string='Course Program', required=True, tracking=True, domain="[('status', '!=', 'discontinued')]")
    course_unit_ids = fields.Many2many('umti.course.units', related='course_id.unit_ids', string='Course Units')
    unit_id = fields.Many2one('umti.course.units', string='Primary Unit', required=False, tracking=False, domain="[('id', 'in', course_unit_ids)]")
    level_id = fields.Many2one('umti.course.level', string='Level', tracking=True)
    academic_year_id = fields.Many2one('umti.academic.year', string='Academic Year', required=True, tracking=True)
    semester_id = fields.Many2one(
        'umti.academic.term', string='Semester / Term', required=True,
        tracking=True,
        domain="[('academic_year_id', '=', academic_year_id),"
               " ('status', '=', 'in_progress')]")
    
    unit_schedule_ids = fields.One2many('umti.assessment.unit.schedule', 'assessment_id', string='Unit Date Schedules')

    date = fields.Date(string='Exam Date', tracking=True)
    
    start_time = fields.Float(string='Start Time', default=8.0, tracking=True)
    duration = fields.Float(string='Duration (Hours)', default=2.0, tracking=True, help="Default duration is 2 hours. Editable for CATs, practicals, or multi-day exams.")
    end_time = fields.Float(string='End Time', compute='_compute_end_time', store=True, readonly=False, tracking=True)

    assessment_type = fields.Selection(
        ASSESSMENT_TYPES, string='Type', required=True, default='cat', tracking=True,
        help="CAT, Assignment and Final Exam compute to the final mark. Other types "
             "must be enabled in the department's assessment plan and are recorded only.")
    
    learning_outcome_type = fields.Selection([
        ('lo1_t', 'LO1 - Theory'),
        ('lo1_p', 'LO1 - Practical'),
        ('lo2_t', 'LO2 - Theory'),
        ('lo2_p', 'LO2 - Practical'),
        ('lo3_t', 'LO3 - Theory'),
        ('lo3_p', 'LO3 - Practical'),
        ('lo4_t', 'LO4 - Theory'),
        ('lo4_p', 'LO4 - Practical'),
        ('cat', 'CAT'),
        ('assignment', 'Assignment'),
        ('final_exam', 'Final Exam'),
    ], string="Outcome / Assessment Category", help="Categorizes where this assessment's marks reflect in the Unit Results sheet.")

    department_id = fields.Many2one(
        related='course_id.department_id', string='Department', store=True, index=True)
    counts_toward_final = fields.Boolean(compute='_compute_effective_weight')
    effective_weight = fields.Float(
        string='Contribution to Final (%)', compute='_compute_effective_weight',
        help="How much this assessment contributes to the final unit mark. The "
             "weight of its component (CAT / Assignment / Final Exam) is shared "
             "equally between all assessments of that type for the unit.")

    category = fields.Selection([
        ('semester_exam', 'Semester Exam'),
        ('periodic', 'Periodic Assessment'),
    ], compute='_compute_category', store=True)

    max_marks = fields.Float(string='Maximum Marks', default=100.0, required=True, tracking=True)
    weight = fields.Float(
        string='Legacy Weight (%)',
        help="Deprecated: weights are now set per department in the Assessment Plan.")
    pass_marks = fields.Float(string='Pass Marks', compute='_compute_pass_marks', store=True, readonly=False)
    pass_marks_manual = fields.Boolean(copy=False)
    pass_marks_warning = fields.Char(compute='_compute_pass_marks_warning')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('open', 'Marking'),
        ('closed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True)

    mark_ids = fields.One2many('umti.assessment.mark', 'assessment_id', string='Student Marks')
    mark_count = fields.Integer(compute='_compute_mark_count', string='Marks Recorded')
    note = fields.Text(string='Internal Notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'The exam code must be unique per company.'),
    ]

    @api.depends('start_time', 'duration')
    def _compute_end_time(self):
        for rec in self:
            if rec.start_time is not False and rec.duration is not False:
                rec.end_time = rec.start_time + rec.duration

    @api.onchange('start_time', 'end_time')
    def _onchange_times(self):
        if self.start_time is not False and self.end_time is not False and self.end_time >= self.start_time:
            self.duration = self.end_time - self.start_time

    @api.depends('assessment_type')
    def _compute_category(self):
        for rec in self:
            rec.category = 'semester_exam' if rec.assessment_type == 'final' else 'periodic'

    @api.depends('max_marks', 'company_id')
    def _compute_pass_marks(self):
        for rec in self:
            if rec.pass_marks_manual:
                continue
            scale = self.env['umti.grade.scale']._get_default(rec.company_id)
            percent = scale.pass_mark if scale else 40.0
            rec.pass_marks = percent * rec.max_marks / 100.0

    @api.depends('pass_marks', 'max_marks', 'company_id')
    def _compute_pass_marks_warning(self):
        for rec in self:
            rec.pass_marks_warning = False
            scale = self.env['umti.grade.scale']._get_default(rec.company_id)
            if scale and rec.max_marks:
                percent = (rec.pass_marks / rec.max_marks) * 100.0
                if abs(percent - scale.pass_mark) > 0.01:
                    rec.pass_marks_warning = _(
                        "Pass mark is %(pct).1f%% (Default scale is %(scale).1f%%).",
                        pct=percent, scale=scale.pass_mark
                    )

    @api.depends('mark_ids')
    def _compute_mark_count(self):
        for rec in self:
            rec.mark_count = len(rec.mark_ids)

    @api.constrains('start_time', 'end_time', 'duration')
    def _check_times(self):
        for rec in self:
            if rec.duration < 0:
                raise ValidationError(_("Duration cannot be negative."))
            if rec.start_time is not False and rec.end_time is not False:
                if rec.start_time >= rec.end_time:
                    raise ValidationError(_("Start time must be strictly before end time."))
                if rec.end_time > 23.99:
                    raise ValidationError(_("End time must be within 24 hours."))

    @api.constrains('max_marks', 'pass_marks', 'weight')
    def _check_marks(self):
        for rec in self:
            if rec.max_marks <= 0:
                raise ValidationError(_("Maximum marks must be greater than zero."))
            if not (0 <= rec.pass_marks <= rec.max_marks):
                raise ValidationError(_("Pass marks must be between 0 and maximum marks."))
            if not (0 <= rec.weight <= 100):
                raise ValidationError(_("Weight percentage must be between 0 and 100."))

    @api.constrains('unit_id', 'course_id', 'semester_id', 'academic_year_id')
    def _check_unit_and_semester_relations(self):
        for rec in self:
            if rec.unit_id and rec.course_id:
                if hasattr(rec.unit_id, 'course_id') and rec.unit_id.course_id and rec.unit_id.course_id != rec.course_id:
                    raise ValidationError(_("The unit must belong to the selected course."))
                elif rec.unit_id not in rec.course_id.unit_ids:
                    raise ValidationError(_("The selected primary unit is not part of the selected course."))
            if rec.semester_id and rec.academic_year_id:
                if hasattr(rec.semester_id, 'academic_year_id') and rec.semester_id.academic_year_id != rec.academic_year_id:
                    raise ValidationError(_("The semester must belong to the selected academic year."))

    @api.depends('assessment_type', 'state', 'semester_id', 'course_id', 'unit_id')
    def _compute_effective_weight(self):
        Plan = self.env['umti.assessment.plan'].sudo()
        for rec in self:
            rec.counts_toward_final = rec.assessment_type in CORE_TYPES
            rec.effective_weight = 0.0
            if (not rec.counts_toward_final or rec.state == 'cancelled'
                    or not rec.semester_id or not rec.course_id.department_id):
                continue
            plan = Plan.search([
                ('semester_id', '=', rec.semester_id.id),
                ('department_id', '=', rec.course_id.department_id.id)], limit=1)
            component = (plan.core_weights() if plan else DEFAULT_CORE_WEIGHTS)[rec.assessment_type]
            siblings = max(1, self.search_count([
                ('unit_id', '=', rec.unit_id.id), ('semester_id', '=', rec.semester_id.id),
                ('course_id', '=', rec.course_id.id),
                ('assessment_type', '=', rec.assessment_type),
                ('state', '!=', 'cancelled')]))
            rec.effective_weight = component / siblings

    @api.constrains('assessment_type', 'semester_id', 'course_id', 'state')
    def _check_type_enabled(self):
        if self.env.context.get('umti_migration'):
            return
        Plan = self.env['umti.assessment.plan']
        for rec in self.filtered(
                lambda r: r.state != 'cancelled' and r.semester_id and r.course_id.department_id):
            plan = Plan._get_or_create(rec.semester_id, rec.course_id.department_id)
            if rec.assessment_type not in plan.enabled_types():
                raise ValidationError(_(
                    "%(type)s is not enabled for %(dept)s in %(sem)s. Ask the Head "
                    "of Department to enable it in the Assessment Plan.",
                    type=dict(ASSESSMENT_TYPES)[rec.assessment_type],
                    dept=rec.course_id.department_id.display_name,
                    sem=rec.semester_id.display_name))

    @api.constrains('assessment_type', 'unit_id', 'semester_id', 'course_id', 'state')
    def _check_one_final(self):
        for rec in self.filtered(
                lambda r: r.assessment_type == 'final' and r.state != 'cancelled' and r.unit_id):
            clash = self.search_count([
                ('id', '!=', rec.id), ('assessment_type', '=', 'final'),
                ('unit_id', '=', rec.unit_id.id), ('semester_id', '=', rec.semester_id.id),
                ('course_id', '=', rec.course_id.id), ('state', '!=', 'cancelled')])
            if clash:
                raise ValidationError(_(
                    "Unit '%(unit)s' already has a Final Exam in semester '%(sem)s'.",
                    unit=rec.unit_id.display_name, sem=rec.semester_id.display_name))

    @api.onchange('assessment_type', 'semester_id', 'course_id')
    def _onchange_assessment_type(self):
        dept = self.course_id.department_id
        if self.assessment_type and self.semester_id and dept:
            plan = self.env['umti.assessment.plan'].sudo().search([
                ('semester_id', '=', self.semester_id.id),
                ('department_id', '=', dept.id)], limit=1)
            if plan and self.assessment_type not in plan.enabled_types():
                return {'warning': {
                    'title': _("Assessment type not enabled"),
                    'message': _(
                        "%(type)s is not enabled for %(dept)s this semester. Ask the "
                        "Head of Department to enable it in the Assessment Plan.",
                        type=dict(ASSESSMENT_TYPES)[self.assessment_type],
                        dept=dept.display_name)}}

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id:
            if self.unit_id and self.unit_id not in self.course_id.unit_ids:
                self.unit_id = False
            self.level_id = self.course_id.course_level_id
            
            existing_units = self.unit_schedule_ids.mapped('unit_id')
            new_lines = [(0, 0, {'unit_id': u.id}) for u in (self.course_id.unit_ids - existing_units)]
            remove_cmds = [(2, line.id) for line in self.unit_schedule_ids if line.unit_id not in self.course_id.unit_ids]
            self.unit_schedule_ids = remove_cmds + new_lines
        else:
            self.unit_id = False
            self.level_id = False
            self.unit_schedule_ids = [(5, 0, 0)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('umti.assessment') or 'New'
            if 'pass_marks' in vals:
                vals['pass_marks_manual'] = True
        return super().create(vals_list)

    def write(self, vals):
        if 'pass_marks' in vals and 'max_marks' not in vals:
            vals = dict(vals, pass_marks_manual=True)
        watch = {'assessment_type', 'learning_outcome_type', 'state', 'unit_id', 'semester_id', 'academic_year_id'}
        need_refresh = watch & set(vals)
        keys = set()
        if need_refresh:
            keys = self.mark_ids._result_keys()
            UnitResult = self.env['umti.unit.result'].sudo()
            for rec in self:
                if rec.unit_id:
                    existing = UnitResult.search([('unit_id', '=', rec.unit_id.id), ('semester_id', '=', rec.semester_id.id)])
                    keys |= {(r.student_id.id, r.unit_id.id, r.semester_id.id, r.academic_year_id.id) for r in existing}
        res = super().write(vals)
        if need_refresh:
            keys |= self.mark_ids._result_keys()
            self.env['umti.unit.result']._refresh(keys)
        return res

    def _check_manager(self):
        if not any(self.env.user.has_group(g) for g in MANAGER_GROUPS):
            raise AccessError(_("Only an exams manager can perform this action."))

    def _has_venue(self):
        self.ensure_one()
        return True

    def action_schedule(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft assessments can be scheduled."))
            if not rec.date or not rec._has_venue() or not rec.end_time:
                raise UserError(_("Please set the date, venue/facility, start time, and end time before scheduling."))
        self.write({'state': 'scheduled'})

    def action_open(self):
        for rec in self:
            if rec.state not in ('draft', 'scheduled'):
                raise UserError(_("Only draft or scheduled assessments can be opened for marking."))
        Mark = self.env['umti.assessment.mark']
        for rec in self:
            students = self.env['school.student'].search([('course_id', '=', rec.course_id.id), ('state', '=', 'active')])
            existing = rec.mark_ids.student_id
            Mark.create([{'assessment_id': rec.id, 'student_id': s.id} for s in (students - existing)])
        self.write({'state': 'open'})

    def action_close(self):
        for rec in self:
            if rec.state != 'open':
                raise UserError(_("Only assessments in marking can be closed."))
            pending = rec.mark_ids.filtered(lambda m: not (m.marked or m.absent))
            if pending:
                raise UserError(_("Every student must be marked or absent before closing. Missing: %s", ", ".join(pending.student_id.mapped('name'))))
        self.write({'state': 'closed'})

    def action_cancel(self):
        self._check_manager()
        if any(rec.state not in ('draft', 'scheduled', 'open') for rec in self):
            raise UserError(_("Only draft, scheduled, or marking assessments can be cancelled."))
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self._check_manager()
        if any(rec.state != 'cancelled' for rec in self):
            raise UserError(_("Only cancelled assessments can be reset to draft."))
        self.write({'state': 'draft'})

    def action_verify_all(self):
        self.mark_ids.filtered(lambda m: m.state == 'draft').action_verify()

    def action_publish_all(self):
        self.mark_ids.filtered(lambda m: m.state == 'verified').action_publish()

    def action_reset_all_draft(self):
        self.mark_ids.filtered(lambda m: m.state != 'draft').action_reset_draft()

    def action_view_marks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Marks Roster"),
            'res_model': 'umti.assessment.mark',
            'view_mode': 'list,form',
            'domain': [('assessment_id', '=', self.id)],
            'context': {'default_assessment_id': self.id},
        }

    def action_open_unit_schedule_popup(self):
        self.ensure_one()
        if self.course_id and self.course_id.unit_ids:
            existing_units = self.unit_schedule_ids.mapped('unit_id')
            missing_units = self.course_id.unit_ids - existing_units
            if missing_units:
                new_lines = [(0, 0, {'unit_id': u.id}) for u in missing_units]
                self.write({'unit_schedule_ids': new_lines})
        return {
            'type': 'ir.actions.act_window',
            'name': _("Configure Unit Exam Dates"),
            'res_model': 'umti.assessment',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('umti_exams.view_umti_assessment_unit_schedule_popup').id, 'form')],
            'target': 'new',
        }