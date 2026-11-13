# -*- coding: utf-8 -*-
from odoo import fields, models


class UmtiCourseRequirementWarningMixin(models.AbstractModel):
    """Reset a course's setup-warning dismissal when a requirement changes.

    The requirement pages are many2many links, so editing or deleting a
    requirement record does not touch the course row. This mixin finds the
    linked courses and makes the warning banner visible again.
    """

    _name = 'umti.course.requirement.warning.mixin'
    _description = 'Course Requirement Warning Reset'

    _warning_course_field = None

    def _linked_courses(self):
        field = self._warning_course_field
        if not field:
            return self.env['umti.course']
        return self.env['umti.course'].search([(field, 'in', self.ids)])

    def write(self, vals):
        res = super().write(vals)
        self._linked_courses().write(
            {'requirements_warning_dismissed': False})
        return res

    def unlink(self):
        courses = self._linked_courses()
        res = super().unlink()
        courses.write({'requirements_warning_dismissed': False})
        return res


class UmtiCourseQualifyingRequirement(models.Model):
    _name = 'umti.course.qualifying.requirement'
    _description = 'Umti Course Qualifying Requirement'
    _inherit = ['umti.course.requirement.warning.mixin']
    _rec_name = 'name'

    _warning_course_field = 'qualifying_requirement_ids'

    name = fields.Char(string='Name', required=True)
    required_mark = fields.Char(string='Required Mark')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    waivable = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


class UmtiCourseGeneralRequirement(models.Model):
    _name = 'umti.course.general.requirement'
    _description = 'Umti Course General Requirement'
    _inherit = ['umti.course.requirement.warning.mixin']
    _rec_name = 'name'

    _warning_course_field = 'general_requirement_ids'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    waivable = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


class UmtiCourseRequiredDocuments(models.Model):
    _name = 'umti.course.required.documents'
    _description = 'Umti Course Required Documents'
    _inherit = ['umti.course.requirement.warning.mixin']
    _rec_name = 'name'

    _warning_course_field = 'document_ids'

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
