from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolAdmissionIntake(models.Model):
    _name = 'school.admission.intake'
    _description = 'Admission Intake'
    _inherit = ['mail.thread']
    _order = 'date_open desc, id desc'

    name = fields.Char(required=True, tracking=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True,
        tracking=True, ondelete='restrict')
    #TODO: Rethink if we really need to link an intake with a semester
    semester_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True, tracking=True,
        ondelete='restrict', domain="[('academic_year_id', '=', academic_year_id)]")
    course_id = fields.Many2one(
        'umti.course', required=True, tracking=True, ondelete='restrict')
    department_id = fields.Many2one(
        related='course_id.department_id', store=True, readonly=True)
    date_open = fields.Date(string='Applications Open', required=True)
    date_close = fields.Date(string='Applications Close', required=True)
    capacity = fields.Integer(help='Maximum number of admitted students. 0 means unlimited.', compute='_compute_counts')
    admission_fee = fields.Monetary(currency_field='currency_id', compute='_compute_requirements')
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'), ('open', 'Open'),
        ('closed', 'Closed'), ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    application_ids = fields.One2many('school.admission.application', 'intake_id')
    application_count = fields.Integer(compute='_compute_counts')
    seats_taken = fields.Integer(compute='_compute_counts')
    seats_left = fields.Integer(compute='_compute_counts')
    required_document_ids = fields.Many2many("umti.course.required.documents", string="Mandatory Documents", compute="_compute_requirements")
    qualifying_requirement_ids = fields.Many2many("umti.course.qualifying.requirement", string="Mandatory Requirements", compute="_compute_requirements")
    general_requirement_ids = fields.Many2many("umti.course.general.requirement", string="General requirements", compute="_compute_requirements")

    @api.depends('course_id')
    def _compute_requirements(self):
        # 1. Fetch the ADMISSION votehead ID once outside the loop
        admission_votehead_id = self.env['umti.structure.votehead'].search([('code', '=', 'ADMISSION')], limit=1).id

        for rec in self:
            if not rec.course_id:
                rec.admission_fee = 0
                rec.required_document_ids = False
                rec.qualifying_requirement_ids = False
                rec.general_requirement_ids = False
                continue  # Skip to the next record immediately
            
            # 2. Map course requirements directly
            rec.qualifying_requirement_ids = rec.course_id.qualifying_requirement_ids
            rec.general_requirement_ids = rec.course_id.general_requirement_ids
            rec.required_document_ids = rec.course_id.document_ids

            # 3. Optimize the admission fee lookup
            if admission_votehead_id:
                # Find the specific structure line matching this course and the ADMISSION votehead code
                fee_line = self.env['umti.fee.structure.line'].search([
                    ('course_id', '=', rec.course_id.id),
                    ('votehead', '=', admission_votehead_id)
                ], limit=1)
                
                rec.admission_fee = fee_line.amount if fee_line else 0
            else:
                rec.admission_fee = 0





    @api.depends('capacity', 'application_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.capacity = rec.course_id.course_capacity if rec.course_id else 0 
            apps = rec.application_ids
            rec.application_count = len(apps)
            rec.seats_taken = len(apps.filtered(
                lambda a: a.state in ('accepted', 'enrolled')))
            rec.seats_left = (rec.capacity - rec.seats_taken) if rec.capacity else 0

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        if self.semester_id and self.semester_id.academic_year_id != self.academic_year_id:
            self.semester_id = False

    @api.constrains('academic_year_id', 'semester_id')
    def _check_semester_in_year(self):
        for rec in self:
            if rec.semester_id.academic_year_id != rec.academic_year_id:
                raise ValidationError(_('The semester does not belong to the selected academic year.'))

    @api.constrains('date_open', 'date_close')
    def _check_dates(self):
        for rec in self:
            if rec.date_close < rec.date_open:
                raise ValidationError(_('The closing date cannot be before the opening date.'))

    def action_open(self):
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Applications'),
            'res_model': 'school.admission.application',
            'view_mode': 'list,form',
            'domain': [('intake_id', '=', self.id)],
            'context': {'default_intake_id': self.id},
        }
