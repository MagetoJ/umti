from odoo import fields, models


class UmtiStudentRecordMixin(models.AbstractModel):
    """Common fields for records that belong to a student and a campus."""

    _name = 'umti.student.record.mixin'
    _description = 'Student Record Mixin'

    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='cascade', index=True, tracking=True)
    course_id = fields.Many2one(
        'umti.course', related='student_id.course_id', store=True,
        readonly=True)
    student_state = fields.Selection(
        related='student_id.state', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    notes = fields.Text()
