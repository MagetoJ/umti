# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError


class UmtiWorkPlan(models.Model):
    _name = 'umti.work.plan'
    _description = 'Master Institutional Work Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name asc'

    name = fields.Char(string='Work Plan Title', required=True, tracking=True)
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True, 
        index=True
    )

    academic_term_id = fields.Many2one('umti.academic.term', string='Academic Term', required=True, tracking=True)
    
    department_id = fields.Many2one('umti.department', string='Primary Department', tracking=True)
    department_ids = fields.Many2many(
        'umti.department',
        'umti_work_plan_department_rel',
        'work_plan_id',
        'department_id',
        string='Applicable Departments',
        help="Leave empty if this plan applies to ALL departments across the institution."
    )
    
    course_unit_id = fields.Many2one('umti.course.units', string='Course Unit', help="Leave empty for Master School Calendar.")
    
    start_date = fields.Date(string='Term Start Date', required=True, tracking=True)
    end_date = fields.Date(string='Term End Date', required=True, tracking=True)
    total_weeks = fields.Integer(string='Total Duration (Weeks)', default=14, required=True)
    
    is_master_plan = fields.Boolean(
        string='Is Master Institutional Plan?',
        default=True,
        help="If checked, this plan applies institute-wide to all departments."
    )

    state = fields.Selection([
        ('draft', 'Draft (Planning)'),
        ('approved', 'Approved (Locked)'),
        ('active', 'Active (In Progress)'),
        ('done', 'Completed')
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many('umti.work.plan.line', 'work_plan_id', string='Master Schedule Lines')
    scheme_ids = fields.One2many('umti.scheme.of.work', 'work_plan_id', string='Generated Schemes of Work')

    def action_approve(self):
        if not self.env.user.has_group('umti_trainers.group_umti_work_plan_manager'):
            raise AccessError(_("Only a School Administrator or Academic Director can approve and lock the Work Plan."))
        self.write({'state': 'approved'})

    def action_reset_to_draft(self):
        if not self.env.user.has_group('umti_trainers.group_umti_work_plan_manager'):
            raise AccessError(_("Only a School Administrator can reset an approved Work Plan to Draft."))
        self.write({'state': 'draft'})

    def action_generate_schemes_of_work(self):
        """
        Seeds Scheme of Work slots across all relevant departments based on the Work Plan.
        """
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("Schemes of Work cannot be generated without an Approved Work Plan."))
        
        SchemeObj = self.env['umti.scheme.of.work']
        DepartmentObj = self.env['umti.department']
        created_schemes = self.env['umti.scheme.of.work']

        target_depts = self.department_ids if self.department_ids else DepartmentObj.search([])

        learning_lines = self.line_ids.filtered(
            lambda l: l.slot_category in ('learning', 'assessment', 'cat') or l.planned_assessment_type == 'other'
        )

        for dept in target_depts:
            for line in learning_lines:
                existing = SchemeObj.search([
                    ('work_plan_id', '=', self.id),
                    ('department_id', '=', dept.id),
                    ('line_ids.work_plan_line_id', '=', line.id)
                ], limit=1)

                if not existing:
                    scheme_vals = {
                        'title': f"[{dept.name}] {self.name} - W{line.week_number}: {line.topic or line.name}",
                        'work_plan_id': self.id,
                        'department_id': dept.id,
                        'unit_id': self.course_unit_id.id if self.course_unit_id else False,
                        'academic_term_id': self.academic_term_id.id,
                        'company_id': self.company_id.id,
                        'state': 'draft',
                        'line_ids': [(0, 0, {
                            'work_plan_line_id': line.id,
                            'week_number': line.week_number,
                            'session_no': 1,
                            'session_title': line.topic or line.name,
                            'learning_outcome': line.subtopics_outline or _('Pending Trainer Outline'),
                            'trainer_activities': line.learning_activities,
                            'resources_refs': line.resources,
                            'planned_assessment_type': line.planned_assessment_type,
                            'other_assessment_name': line.other_assessment_name,
                        })]
                    }
                    scheme = SchemeObj.create(scheme_vals)
                    created_schemes |= scheme
                else:
                    created_schemes |= existing

        self.write({'state': 'active'})

        return {
            'name': _('Generated Schemes of Work'),
            'type': 'ir.actions.act_window',
            'res_model': 'umti.scheme.of.work',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_schemes.ids)],
        }


class UmtiWorkPlanLine(models.Model):
    _name = 'umti.work.plan.line'
    _description = 'Work Plan Schedule Line'
    _order = 'week_number asc, sequence asc, id asc'

    sequence = fields.Integer(string='Sequence', default=10)
    work_plan_id = fields.Many2one(
        'umti.work.plan', 
        string='Work Plan', 
        required=True, 
        ondelete='cascade', 
        index=True
    )
    name = fields.Char(string='Activity / Unit Module Title', required=True)
    week_number = fields.Integer(string='Week No.', required=True, default=1)
    topic = fields.Char(string='Topic / Module')
    subtopics_outline = fields.Text(string='Subtopics / Content Outline')
    learning_activities = fields.Text(string='Learning Activities')
    resources = fields.Char(string='Resources / Materials')

    slot_category = fields.Selection([
        ('learning', 'Teaching & Learning Slot'),
        ('assessment', 'Continuous Assessment (CAT / Assignment)'),
        ('cat', 'CAT Session'),
        ('break', 'Holiday / Mid-Term Break'),
        ('exam', 'Final Examination Week')
    ], string='Slot Category', default='learning', required=True)

    planned_assessment_type = fields.Selection([
        ('none', 'None'),
        ('cat', 'Continuous Assessment Test (CAT)'),
        ('assignment', 'Assignment'),
        ('final_exam', 'Final Exam'),
        ('other', 'Other Assessment')
    ], string='Assessment Type', default='none')

    other_assessment_name = fields.Char(string='Other Assessment Title')
