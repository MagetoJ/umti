# -*- coding: utf-8 -*-
from odoo import api,fields,models,_
from odoo.exceptions import UserError

class UmtiCourse(models.Model):
    _name = 'umti.course'
    _description = 'Umti Course'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string="Name", required = True, tracking=True)
    code = fields.Char(string="Code", required = True, copy=False, tracking=True)
    department_id = fields.Many2one("umti.department", string="Department", required=True, tracking=True)
    course_level_id = fields.Many2one("umti.course.level", string="Course Level", required=True, tracking=True)
    minimum_credits = fields.Integer(string="Minimum Credits", required=True, tracking=True, help="Minimum credits required to graduate from this course")
    period_type = fields.Selection([('months', 'Months'), ('years', 'Years')], default="years", required=True, tracking=True)
    period = fields.Integer('Period', default=0, tracking=True)
    qualifying_requirement_ids = fields.Many2many( comodel_name='umti.course.qualifying.requirement', relation='umti_course_qualifying_rel', 
        column1='course_id', column2='requirement_id', string="Qualifying Requirements")
    
    general_requirement_ids = fields.Many2many( comodel_name='umti.course.general.requirement',relation='umti_course_general_rel', column1='course_id', 
        column2='requirement_id',string="General Requirements")
    document_ids = fields.Many2many( comodel_name='umti.course.required.documents',relation='umti_course_document_rel', column1='course_id', 
        column2='document_id',string="Required Documents")
    unit_ids = fields.Many2many(comodel_name='umti.course.units', relation='umti_course_unit_rel', column1='course_id', column2='unit_id', string="Units")
    course_capacity = fields.Integer(string="Course Capacity", tracking=True, default=0, copy=False)
    course_quorum = fields.Integer(string="Course Quorum", tracking=True, default=1, copy=False)
    quorum_progress = fields.Integer(string="Course Quorum", compute="_compute_counts",)
    status = fields.Selection([('draft', 'Draft'),('active', 'Active'),('discontinued', 'Discontinued')], default='draft', string="Status", tracking=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)
    unit_credit_totals = fields.Integer(string="Unit Credits", compute="_compute_counts",)
    totals_progress = fields.Integer(string="Unit Credits", compute="_compute_counts",)
    active = fields.Boolean(default=True, tracking=True)


    def _compute_counts(self):
        for record in self:
            if record.unit_ids:
                record.unit_credit_totals = sum(unit.credit_contribution for unit in record.unit_ids)
                if record.minimum_credits:
                    record.totals_progress = (record.unit_credit_totals / record.minimum_credits) * 100
                else:
                    record.totals_progress = 0
            else:
                record.unit_credit_totals = 0
                record.totals_progress = 0

            # Compute Quorum Progress
            if record.course_capacity and record.course_quorum:
                record.quorum_progress = (record.course_quorum / record.course_capacity) * 100
            else:
                record.quorum_progress = 0


    #automatically compute period if period_type is changed
    @api.onchange('period_type')
    def _onchange_period_type(self):
        """
        This method is called when the period_type field is changed.
        It automatically computes the period field based on the period_type field.
        """

        if not self.period:
            return

        if self.period_type == 'years':
            self.period = max(1, int(self.period / 12))
        elif self.period_type == 'months':
            self.period = self.period * 12
    
    def activate_course(self):
        for course in self:
            if not course.minimum_credits:
                raise UserError(_('Minimum Credits is not set.'))
            if not course.period:
                raise UserError(_('Course Period is not set.'))
            if not course.course_capacity:
                raise UserError(_('Mandated Capacity is not set.'))
            course.write({'active': True})
            if not any(course.unit_ids):
                raise UserError(_('Units are not set.'))            
            if course.unit_credit_totals < course.minimum_credits:
                raise UserError(_('Unit Credits set so far is less than Minimum Credits.'))            
            if not any(course.qualifying_requirement_ids):
                raise UserError(_('Qualifying Requirements are not set.'))
        self.write({'status': 'active'})

    #later on, prevent discontinuing a course if it has student
    def discontinue_course(self):
        pass