from odoo import fields, models


class UmtiCourseInherit(models.Model):
    _inherit = 'umti.course'

    student_count = fields.Integer(
        compute='_compute_student_count', string='Students')

    def _compute_student_count(self):
        Student = self.env['school.student']
        for course in self:
            course.student_count = Student.search_count([
                ('course_id', '=', course.id),
                ('state', '=', 'active'),
            ])
