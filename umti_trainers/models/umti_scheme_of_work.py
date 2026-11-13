# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError


class UmtiSchemeOfWork(models.Model):
    _name = 'umti.scheme.of.work'
    _description = 'Trainer Scheme of Work'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_term_id desc, create_date desc'

    title = fields.Char(string='Scheme Title', required=True, tracking=True)
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True, 
        index=True
    )
    
    work_plan_id = fields.Many2one(
        'umti.work.plan', 
        string='Source Work Plan', 
        ondelete='cascade', 
        required=True,
        readonly=True,
        help="Institutional Work Plan baseline from which this scheme was generated."
    )
    
    trainer_id = fields.Many2one(
        'res.users', 
        string='Assigned Trainer', 
        default=lambda self: self.env.user, 
        required=True, 
        tracking=True
    )
    
    department_id = fields.Many2one('umti.department', string='Department', tracking=True)
    unit_id = fields.Many2one('umti.course.units', string='Course Unit / Subject', tracking=True)
    academic_term_id = fields.Many2one('umti.academic.term', string='Academic Term', required=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Revision Requested')
    ], string='Status', default='draft', tracking=True)

    # Alias to prevent view field mismatch errors
    status = fields.Selection(related='state', string='Status Alias', readonly=True)

    line_ids = fields.One2many(
        'umti.scheme.of.work.line', 
        'scheme_id', 
        string='Weekly Pedagogical Breakdown'
    )

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("You cannot submit an empty Scheme of Work."))
            rec.write({'state': 'submitted'})

    def action_approve(self):
        if not self.env.user.has_group('umti_trainers.group_umti_work_plan_manager'):
            raise AccessError(_("Only Academic Heads or Directors can approve Schemes of Work."))
        self.write({'state': 'approved'})

    def action_reject(self):
        if not self.env.user.has_group('umti_trainers.group_umti_work_plan_manager'):
            raise AccessError(_("Only Academic Heads can request revisions on Schemes of Work."))
        self.write({'state': 'rejected'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})


class UmtiSchemeOfWorkLine(models.Model):
    _name = 'umti.scheme.of.work.line'
    _description = 'Scheme of Work Weekly Detail'
    _order = 'week_number asc, session_no asc'

    scheme_id = fields.Many2one(
        'umti.scheme.of.work', 
        string='Scheme of Work', 
        ondelete='cascade', 
        required=True
    )
    company_id = fields.Many2one('res.company', string='Company', related='scheme_id.company_id', store=True)

    work_plan_line_id = fields.Many2one(
        'umti.work.plan.line', 
        string='Work Plan Activity Slot', 
        ondelete='set null'
    )

    week_number = fields.Integer(string='Week No.', required=True)
    session_no = fields.Integer(string='Lesson / Session No.', default=1)
    session_title = fields.Char(string='Topic / Unit Title', required=True)
    
    learning_outcome = fields.Text(string='Expected Learning Outcomes', required=True)
    trainer_activities = fields.Text(string='Teaching & Learning Activities')
    resources_refs = fields.Char(string='Instructional Media & Equipment')

    planned_assessment_type = fields.Selection([
        ('none', 'N/A - Regular Lesson'),
        ('cat', 'Continuous Assessment Test (CAT)'),
        ('assignment', 'Practical Project / Assignment'),
        ('exam', 'Final Examination Session'),
        ('other', 'Other Assessment')
    ], string='Assessment Type', default='none')

    other_assessment_name = fields.Char(string='Assessment Details')
    notes = fields.Text(string='Self-Evaluation / Remarks')
