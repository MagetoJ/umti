# -*- coding: utf-8 -*-
from odoo import fields, models, api,_
from odoo.exceptions import UserError


class UmtiCourseUnits(models.Model):
    _name = 'umti.course.units'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _description = 'UMTI Course Units'
    
    name = fields.Char(string='Name', tracking=True, required=True)
    code = fields.Char(string='Code', tracking=True, required=True)
    unit_type = fields.Selection([('theory', 'Theory'), ('practical', 'Practical'), ('project', 'Project'),('attachment', 'Attachment'), ('other', 'Other')],
                                  string='Unit Type', default='theory', tracking=True)
    
    unit_level = fields.Selection([('yr_one', 'Year 1'), ('yr_two', 'Year 2'), ('yr_three', 'Year 3'), ('yr_four', 'Year 4'), ('other', 'Other')],
                                  string='Unit Level', default='yr_one', tracking=True)
    unit_semester = fields.Selection([('sem_1', 'Semester 1'), ('sem_2', 'Semester 2'), ('sem_3', 'Semester 3'), ('sem_4', 'Semester 4'), ('other', 'Other')],  
                                     string='Unit Semester', default='sem_1', tracking=True) #Refine Logic to match semeter generation
    course_ids = fields.Many2many(
        'umti.course', relation='umti_course_unit_rel',
        column1='unit_id', column2='course_id', string='Courses',
        help="Courses that include this unit. Placement inside each course "
             "is set on the course's Unit Plan.")
    department_ids = fields.Many2many(
        'umti.department', 'umti_course_units_department_rel',
        'unit_id', 'department_id', string='Departments', tracking=True)
    department_id = fields.Many2one(
        'umti.department', string='Primary Department', tracking=True,
        help="Single department used where the process needs one "
             "(attendance sheets, trainer assignment). Kept in sync with "
             "Departments.")

    credit_contribution = fields.Integer(string='Credit Contribution', tracking=True, default=0)
    active = fields.Boolean(default=True, tracking=True,)

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Code must be unique.'),
    ]
    @api.model_create_multi
    def create(self, vals_list):
        units = super().create(vals_list)
        for unit in units:
            if unit.department_ids:
                if (not unit.department_id
                        or unit.department_id not in unit.department_ids):
                    unit.department_id = unit.department_ids[:1]
            elif unit.department_id:
                unit.department_ids = [(4, unit.department_id.id)]
        return units

    def write(self, vals):
        res = super().write(vals)
        if 'department_ids' in vals:
            for unit in self:
                if (unit.department_id
                        and unit.department_id not in unit.department_ids):
                    unit.department_id = unit.department_ids[:1]
                elif not unit.department_id and unit.department_ids:
                    unit.department_id = unit.department_ids[:1]
        elif 'department_id' in vals:
            for unit in self:
                if (unit.department_id
                        and unit.department_id not in unit.department_ids):
                    unit.department_ids = [(4, unit.department_id.id)]
        return res

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
