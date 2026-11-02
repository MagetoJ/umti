from odoo import models, fields, api, _
from odoo.exceptions import UserError


class UMTIWorkPlan(models.Model):
    _name = 'umti.work.plan'
    _description = 'Work Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Plan Title', required=True, tracking=True)
    scheme_id = fields.Many2one('umti.scheme.of.work', string='Scheme of Work', domain="[('state', '=', 'approved')]", tracking=True)
    trainer_id = fields.Many2one('res.users', string='Trainer', default=lambda self: self.env.user, required=True, tracking=True)
    tel_no = fields.Char(string='Telephone No.')
    department_id = fields.Many2one('umti.department', string='Department', required=True, tracking=True)
    hod_id = fields.Many2one('res.users', string='Head of Department', compute='_compute_hod_id', store=True)

    academic_term_id = fields.Many2one('umti.academic.term', string='Academic Term', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    course_unit_id = fields.Many2one('umti.course.units', string='Course Unit', tracking=True)
    unit_code = fields.Char(string='Unit Code', related='course_unit_id.code', store=True, readonly=True)
    class_name = fields.Char(string='Class / Intended Group')

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')

    skill_or_job_task = fields.Text(string='Skill / Job Task')
    benchmark_criteria = fields.Text(string='Benchmark / Assessment Criteria')
    objectives = fields.Text(string='Term Objectives & Goals')

    scheme_of_work_ids = fields.One2many('umti.scheme.of.work', 'work_plan_id', string='Linked Schemes of Work')
    line_ids = fields.One2many('umti.work.plan.line', 'work_plan_id', string='Session Activities')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Revision Requested'),
    ], default='draft', tracking=True)

    rejection_reason = fields.Text(string='HOD Feedback', tracking=True)

    prepared_by_id = fields.Many2one('res.users', string='Prepared By', default=lambda self: self.env.user, readonly=True)
    prepared_date = fields.Date(string='Prepared Date', default=fields.Date.context_today, readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approved_date = fields.Date(string='Approved Date', readonly=True, tracking=True)

    @api.depends('department_id')
    def _compute_hod_id(self):
        for record in self:
            record.hod_id = record.department_id.manager_id or record.department_id.hod_id

    def action_submit(self):
        for record in self:
            record.state = 'submitted'
            if record.hod_id:
                record.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=record.hod_id.id,
                    summary=_('Work Plan Approval Required'),
                    note=f'Please review the Work Plan for {record.name}.'
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
                raise UserError(_("Please enter revision feedback for the trainer."))
            record.state = 'rejected'
            record.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reset_draft(self):
        for record in self:
            record.state = 'draft'


class UMTIWorkPlanLine(models.Model):
    _name = 'umti.work.plan.line'
    _description = 'Work Plan Session Line'

    work_plan_id = fields.Many2one('umti.work.plan', string='Work Plan', ondelete='cascade')
    session_date = fields.Date(string='Scheduled Date', required=True)
    time_slot = fields.Char(string='Time / Period')
    specific_objective = fields.Text(string='Session Objective', required=True)
    activity = fields.Text(string='Trainer & Learner Activities')
    venue = fields.Char(string='Classroom / Lab')