# -*- coding: utf-8 -*-
from odoo import fields, models, api,_
from odoo.exceptions import UserError


class UmtiCourseUnits(models.Model):
    _name = 'umti.course.units'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', tracking=True, required=True)
    code = fields.Char(string='Code', tracking=True, required=True)
    unit_type = fields.Selection([('theory', 'Theory'), ('practical', 'Practical'), ('project', 'Project'),('attachment', 'Attachment'), ('other', 'Other')],
                                  string='Unit Type', default='theory', tracking=True)
    
    unit_level = fields.Selection([('yr_one', 'Year 1'), ('yr_two', 'Year 2'), ('yr_three', 'Year 3'), ('yr_four', 'Year 4'), ('other', 'Other')],
                                  string='Unit Level', default='yr_one', tracking=True)
    unit_semester = fields.Selection([('sem_1', 'Semester 1'), ('sem_2', 'Semester 2'), ('sem_3', 'Semester 3'), ('sem_4', 'Semester 4'), ('other', 'Other')],  
                                     string='Unit Semester', default='sem_1', tracking=True) #Refine Logic to match semeter generation
    department_id = fields.Many2one('umti.department', string='Department', tracking=True)
    credit_contribution = fields.Integer(string='Credit Contribution', tracking=True, default=0)
    active = fields.Boolean(default=True, tracking=True,)

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Code must be unique.'),
    ]
    #prevent creating a unit without credit contribution
    @api.constrains('credit_contribution')
    def _check_credit_contribution(self):
        for unit in self:
            if not unit.credit_contribution:
                raise UserError(_('Credit Contribution is not set.'))
            
    def write(self, vals):
        res = super(UmtiCourseUnits, self).write(vals)
        if 'credit_contribution' in vals:
             self._check_credit_contribution()
        return res

    #prevent deleting a unit if it has courses and students
    @api.constrains('active')
    def _check_active(self):
        for unit in self:
                pass
