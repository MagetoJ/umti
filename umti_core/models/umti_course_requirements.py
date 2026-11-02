# -*- coding: utf-8 -*-
from odoo import fields, models


class UmtiCourseQualifyingRequirement(models.Model):
    _name = 'umti.course.qualifying.requirement'
    _description = 'Umti Course Qualifying Requirement'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    required_mark = fields.Char(string='Required Mark')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    waivable = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


class UmtiCourseGeneralRequirement(models.Model):
    _name = 'umti.course.general.requirement'
    _description = 'Umti Course General Requirement'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    waivable = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


class UmtiCourseRequiredDocuments(models.Model):
    _name = 'umti.course.required.documents'
    _description = 'Umti Course Required Documents'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(
        string='Code', index=True,
        help="Stable identifier used by admissions (e.g. kcse, passport). "
             "Do not change it once applications exist.")
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    waivable = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'The document code must be unique per company.'),
    ]
