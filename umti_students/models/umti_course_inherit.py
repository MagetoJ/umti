# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UmtiCourse(models.Model):
    _inherit = 'umti.course'

    student_ids = fields.One2many('school.student', 'course_id', string='Students')
    enrolled_student_count = fields.Integer(
        string="Enrolled Student Count",
        compute="_compute_enrolled_students",
        store=True
    )

    @api.depends('student_ids')
    def _compute_enrolled_students(self):
        for course in self:
            course.enrolled_student_count = len(course.student_ids)

    def action_view_registered_students(self):
        self.ensure_one()
        return {
            'name': _('Registered Students'),
            'type': 'ir.actions.act_window',
            'res_model': 'school.student',
            'view_mode': 'kanban,list,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id},
        }

    def discontinue_course(self):
        for course in self:
            if course.enrolled_student_count > 0:
                raise UserError(_('Cannot discontinue a course that has enrolled students.'))
        return super().discontinue_course()

#: States where an application is still being worked on.
OPEN_STATES = ('draft', 'submitted', 'review')


class UmtiCourseInherit(models.Model):
    _inherit = 'umti.course'

    def write(self, vals):
        res = super().write(vals)
        requirement_fields = {
            'document_ids',
            'qualifying_requirement_ids',
            'general_requirement_ids',
        }
        if requirement_fields & set(vals):
            # Requirements changed on the course: bring the applications
            # still in play in line, otherwise the applicant never sees the
            # new document/requirement and staff only find out at review.
            applications = self.env['school.admission.application'].search([
                ('course_id', 'in', self.ids),
                ('state', 'in', OPEN_STATES),
            ])
            applications._sync_requirement_lines()
        return res
