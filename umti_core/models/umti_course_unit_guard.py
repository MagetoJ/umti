from odoo import _, api, models
from odoo.exceptions import ValidationError


class UmtiCourseUnitGuard(models.AbstractModel):
    _name = 'umti.course.unit.guard'
    _description = 'Course-Unit Integrity Guard'

    @api.constrains('unit_id', 'course_id')
    def _check_unit_in_course(self):
        for rec in self:
            unit = rec.unit_id
            course = rec.course_id
            if unit and course and unit not in course.unit_ids:
                raise ValidationError(_(
                    'Unit "%(unit)s" does not belong to course "%(course)s".',
                    unit=unit.display_name,
                    course=course.display_name,
                ))
