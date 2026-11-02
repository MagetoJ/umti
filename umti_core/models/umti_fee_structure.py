# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class UmtiFeeStructure(models.Model):
    _name = 'umti.fee.structure'
    _description = 'Umti Fee Structure'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, tracking=True) #change this to sequence later
    code = fields.Char(string='Code', required=True, tracking=True)
    status = fields.Selection([('draft', 'Draft'),('approved', 'Approved'),('closed', 'Closed')], default='draft', string="Status", tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    structure_line_ids = fields.One2many('umti.fee.structure.line', 'structure_id', string="Structure Lines")
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Code must be unique.'),
    ]

    def approve_fee_structure(self):
        for structure in self:
            if not structure.structure_line_ids:
                raise UserError(_('Fee Structure Lines are not set.'))
            structure.write({'status': 'approved'})

    def close_fee_structure(self):
        for structure in self:
            #we  will check if there is an active semester using this fee structure
            structure.write({'status': 'closed'})

class UmtiStructureVotehead(models.Model):
    _name = 'umti.structure.votehead'
    _description = 'Umti Structure Votehead'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


class UmtiFeeStructureLine(models.Model):
    _name = 'umti.fee.structure.line'
    _description = 'Umti Fee Structure Line'
    _rec_name = 'academic_year_id'

    academic_year_id = fields.Many2one('umti.academic.year', string="Academic Year", required=True)
    semester_id = fields.Many2one('umti.academic.term', string="Semester",domain="[('academic_year_id','=',academic_year_id),('status','=','in_progress'),('active','=',True)]")
    course_id = fields.Many2one('umti.course', string="Course", required=True)
    structure_id = fields.Many2one('umti.fee.structure', string="Structure", required=True)
    votehead = fields.Many2one('umti.structure.votehead', string="Voteheads", required=True)
    department_id = fields.Many2one('umti.department', string="Department", required=True)
    amount = fields.Monetary(string="Amount", required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string="Currency", required=True, default=lambda self: self.env.user.company_id.currency_id)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)
