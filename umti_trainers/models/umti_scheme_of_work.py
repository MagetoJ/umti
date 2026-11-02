from odoo import models, fields, api, _
from odoo.exceptions import UserError


class UMTISchemeOfWork(models.Model):
    _name = 'umti.scheme.of.work'
    _description = 'Scheme of Work'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    title = fields.Char(string='Title', required=True, tracking=True)
    work_plan_id = fields.Many2one('umti.work.plan', string='Related Work Plan', tracking=True)
    trainer_id = fields.Many2one('res.users', string='Trainer', default=lambda self: self.env.user, required=True, tracking=True)
    tel_no = fields.Char(string='Telephone No.')
    department_id = fields.Many2one('umti.department', string='Department', required=True, tracking=True)
    course_id = fields.Many2one('umti.course', string='Course / Trade', tracking=True)
    unit_id = fields.Many2one('umti.course.units', string='Unit / Subject', required=True, tracking=True)
    unit_code = fields.Char(string='Unit Code', related='unit_id.code', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # Class & Schedule Metadata
    academic_term_id = fields.Many2one('umti.academic.term', string='Academic Term', required=True, tracking=True)
    class_name = fields.Char(string='Class / Intended Group')
    level = fields.Char(string='Level / Qualification')
    number_of_trainees = fields.Integer(string='Number of Trainees')
    date_of_preparation = fields.Date(string='Date of Preparation', default=fields.Date.context_today)
    date_of_revision = fields.Date(string='Date of Revision')

    # Task & Criteria
    skill_or_job_task = fields.Text(string='Skill / Job Task')
    benchmark_criteria = fields.Text(string='Benchmark / Assessment Criteria')

    # Status & Approvals
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Revision Requested'),
    ], default='draft', tracking=True)

    rejection_reason = fields.Text(string='HOD Feedback / Revision Notes', tracking=True)

    prepared_by_id = fields.Many2one('res.users', string='Prepared By', default=lambda self: self.env.user, readonly=True)
    prepared_date = fields.Date(string='Prepared Date', default=fields.Date.context_today, readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approved_date = fields.Date(string='Approved Date', readonly=True, tracking=True)

    hod_id = fields.Many2one('res.users', string='Head of Department', compute='_compute_hod_id', store=True)
    line_ids = fields.One2many('umti.scheme.of.work.line', 'scheme_id', string='Weekly Plan')

    @api.depends('department_id')
    def _compute_hod_id(self):
        for record in self:
            record.hod_id = record.department_id.manager_id or record.department_id.hod_id

    def action_submit(self):
        for record in self:
            if not record.line_ids:
                raise UserError(_("You cannot submit an empty Scheme of Work. Please add weekly topics."))
            record.state = 'submitted'
            if record.hod_id:
                record.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=record.hod_id.id,
                    summary=_('Scheme of Work Approval Required'),
                    note=f'Please review and approve the Scheme of Work for {record.title}.'
                )

    def action_approve(self):
        for record in self:
            record.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Date.today(),
            })
            record.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reject(self):
        for record in self:
            if not record.rejection_reason:
                raise UserError(_("Please provide feedback or a reason for revision before requesting changes."))
            record.state = 'rejected'
            record.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reset_draft(self):
        for record in self:
            record.state = 'draft'


class UMTISchemeOfWorkLine(models.Model):
    _name = 'umti.scheme.of.work.line'
    _description = 'Scheme of Work Line Item'

    scheme_id = fields.Many2one('umti.scheme.of.work', string='Scheme of Work', ondelete='cascade')
    week_number = fields.Integer(string='Week No.', required=True)
    session_no = fields.Integer(string='Session No.')
    session_title = fields.Char(string='Session Title / Topic', required=True)
    learning_outcome = fields.Text(string='Learning Outcome')
    trainer_activities = fields.Text(string='Trainer Activities')
    trainee_activities = fields.Text(string='Trainee Activities')
    resources_refs = fields.Text(string='Resources & References')
    learning_checks = fields.Text(string='Learning Checks / Assessment')
    reflections_date = fields.Date(string='Reflections / Date Conducted')