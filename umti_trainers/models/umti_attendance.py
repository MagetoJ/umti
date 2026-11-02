from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class UmtiAttendanceSheet(models.Model):
    _name = 'umti.attendance.sheet'
    _description = 'Attendance Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(
        string='Session Title', required=True, tracking=True)
    date = fields.Date(
        string='Date', required=True,
        default=fields.Date.context_today, tracking=True)
    trainer_id = fields.Many2one(
        'res.users', string='Trainer', required=True, tracking=True,
        domain="[('share', '=', False)]",
        default=lambda self: self.env.user)
    department_id = fields.Many2one(
        'umti.department', string='Department',
        required=True, tracking=True)
    course_id = fields.Many2one(
        'umti.course', string='Course', required=True, tracking=True,
        domain="[('department_id', '=', department_id)]")
    unit_id = fields.Many2one(
        'umti.course.units', string='Unit', required=True, tracking=True,
        domain="[('id', 'in', allowed_unit_ids)]")
    allowed_unit_ids = fields.Many2many(
        'umti.course.units', compute='_compute_allowed_unit_ids')
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester',
        required=True, tracking=True,
        domain="[('status', '=', 'in_progress')]")
    line_ids = fields.One2many(
        'umti.attendance.line', 'sheet_id', string='Attendance Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Submitted'),
    ], default='draft', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    present_count = fields.Integer(
        compute='_compute_counts', string='Present')
    absent_count = fields.Integer(
        compute='_compute_counts', string='Absent')
    total_count = fields.Integer(
        compute='_compute_counts', string='Total')

    # Fields that may not change once the sheet is submitted.
    _SUBMITTED_LOCKED_FIELDS = {
        'name', 'date', 'trainer_id', 'department_id', 'course_id',
        'unit_id', 'academic_term_id', 'line_ids',
    }

    def write(self, vals):
        if self._SUBMITTED_LOCKED_FIELDS & set(vals) and not self.env.context.get('umti_attendance_force'):
            if any(rec.state == 'done' for rec in self):
                raise UserError(_(
                    "A submitted attendance sheet cannot be edited. "
                    "Reset it to draft first."))
        return super().write(vals)

    @api.constrains('trainer_id', 'unit_id', 'academic_term_id', 'date', 'name')
    def _check_duplicate_sheet(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id), ('trainer_id', '=', rec.trainer_id.id),
                ('unit_id', '=', rec.unit_id.id),
                ('academic_term_id', '=', rec.academic_term_id.id),
                ('date', '=', rec.date), ('name', '=', rec.name),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    "An attendance sheet titled '%(name)s' already exists for "
                    "%(unit)s on %(date)s. Change the session title if this is "
                    "a second session on the same day.",
                    name=rec.name, unit=rec.unit_id.display_name, date=rec.date))

    @api.depends('course_id', 'course_id.unit_ids')
    def _compute_allowed_unit_ids(self):
        for rec in self:
            rec.allowed_unit_ids = (
                rec.course_id.unit_ids if rec.course_id else False)

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id:
            if self.unit_id and self.unit_id not in self.course_id.unit_ids:
                self.unit_id = False
        else:
            self.unit_id = False

    @api.onchange('unit_id', 'academic_term_id')
    def _onchange_fetch_enrolled_students(self):
        self._populate_roster()

    def _get_roster_enrollments(self):
        """Active enrollments that make up this sheet's roster.

        Extension point: other modules can widen how the roster is found.
        """
        self.ensure_one()
        if not (self.unit_id and self.academic_term_id):
            return self.env['umti.student.unit.enrollment']
        return self.env['umti.student.unit.enrollment'].search([
            ('unit_id', '=', self.unit_id.id),
            ('academic_term_id', '=', self.academic_term_id.id),
            ('state', '=', 'enrolled'),
        ])

    def _populate_roster(self):
        if not (self.unit_id and self.academic_term_id):
            return
        lines = [(5, 0, 0)]
        for enrollment in self._get_roster_enrollments():
            lines.append((0, 0, {'student_id': enrollment.student_id.id}))
        self.line_ids = lines

    def action_populate_roster(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Roster can only be refreshed while in Draft state."))
            if not (rec.unit_id and rec.academic_term_id):
                raise UserError(_(
                    "Please select a Unit and Semester first."))
            enrollments = rec._get_roster_enrollments()
            if not enrollments:
                raise UserError(_(
                    "No enrolled students found for %(unit)s in %(term)s. "
                    "Check that students are enrolled in this unit for the "
                    "term (Trainer Workspace > Unit Enrollments).",
                    unit=rec.unit_id.name, term=rec.academic_term_id.name))
            rec.line_ids.unlink()
            self.env['umti.attendance.line'].create([{
                'sheet_id': rec.id,
                'student_id': e.student_id.id,
            } for e in enrollments])

    def action_submit_attendance(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_(
                    "Cannot submit attendance with an empty roster. "
                    "Please fetch enrolled students first."))
            rec.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    @api.depends('line_ids.status_id.is_present')
    def _compute_counts(self):
        for rec in self:
            rec.total_count = len(rec.line_ids)
            rec.present_count = len(
                rec.line_ids.filtered(lambda l: l.status_id.is_present))
            rec.absent_count = len(
                rec.line_ids.filtered(lambda l: not l.status_id.is_present))

    def action_view_students(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enrolled Students'),
            'res_model': 'umti.student.unit.enrollment',
            'view_mode': 'list,form',
            'domain': [
                ('unit_id', '=', self.unit_id.id),
                ('academic_term_id', '=', self.academic_term_id.id),
                ('state', '=', 'enrolled'),
            ],
        }


class UmtiAttendanceLine(models.Model):
    _name = 'umti.attendance.line'
    _description = 'Attendance Line'
    _order = 'date desc, id'

    sheet_id = fields.Many2one(
        'umti.attendance.sheet', string='Attendance Sheet',
        required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one(
        'school.student', string='Student', required=True)
    date = fields.Date(
        related='sheet_id.date', string='Date', store=True)
    course_id = fields.Many2one(
        related='sheet_id.course_id', string='Course')
    unit_id = fields.Many2one(
        related='sheet_id.unit_id', string='Unit')
    academic_term_id = fields.Many2one(
        related='sheet_id.academic_term_id', string='Semester')
    sheet_state = fields.Selection(
        related='sheet_id.state', string='Sheet Status')
    status_id = fields.Many2one(
        'umti.attendance.status', string='Status', required=True,
        ondelete='restrict', index=True,
        default=lambda self: self.env['umti.attendance.status']._get_default())
    is_present = fields.Boolean(
        related='status_id.is_present', string='Present', store=True)
    counts_in_rate = fields.Boolean(
        related='status_id.counts_in_rate', string='Counts in Rate', store=True)
    absence_reason = fields.Char(string='Reason for Absence')
    remarks = fields.Char(string='Remarks')

    # Denormalised from the sheet so students, reports and pivots can
    # group and filter without joining through the sheet every time.
    date = fields.Date(related='sheet_id.date', store=True, index=True)
    sheet_state = fields.Selection(
        related='sheet_id.state', string='Sheet Status', store=True)
    unit_id = fields.Many2one(related='sheet_id.unit_id', store=True)
    course_id = fields.Many2one(related='sheet_id.course_id', store=True)
    department_id = fields.Many2one(related='sheet_id.department_id', store=True)
    academic_term_id = fields.Many2one(related='sheet_id.academic_term_id', store=True)
    trainer_id = fields.Many2one(related='sheet_id.trainer_id', store=True)

    _sql_constraints = [
        ('sheet_student_uniq', 'unique(sheet_id, student_id)',
         'A student can only appear once on an attendance sheet.'),
    ]

    _EDITABLE_FIELDS = {'student_id', 'sheet_id', 'status_id', 'absence_reason', 'remarks'}

    def _check_sheet_open(self):
        if self.env.context.get('umti_attendance_force'):
            return
        if any(line.sheet_id.state == 'done' for line in self):
            raise UserError(_(
                "This attendance sheet has been submitted. "
                "Reset it to draft to change attendance."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_sheet_open()
        return records

    def write(self, vals):
        if self._EDITABLE_FIELDS & set(vals):
            self._check_sheet_open()
        return super().write(vals)

    def unlink(self):
        self._check_sheet_open()
        return super().unlink()

    @api.onchange('status_id')
    def _onchange_status_id(self):
        if self.status_id.is_present:
            self.absence_reason = False
