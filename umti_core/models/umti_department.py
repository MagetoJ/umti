# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class UmtiDepartment(models.Model):
    _name = 'umti.department'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, index=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Code must be unique.'),
    ]

    #prevent deleting a department if it has courses
    @api.constrains('active')
    def _check_active(self):
        pass