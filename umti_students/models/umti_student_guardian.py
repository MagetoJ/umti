from odoo import fields, models


class SchoolStudentGuardian(models.Model):
    """A guardian or emergency contact of a student."""
    _name = 'school.student.guardian'
    _description = 'Student Guardian / Emergency Contact'

    student_id = fields.Many2one(
        'school.student', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True)
    relationship = fields.Selection([
        ('parent', 'Parent'),
        ('guardian', 'Guardian'),
        ('sibling', 'Sibling'),
        ('spouse', 'Spouse'),
        ('other', 'Other'),
    ], required=True, default='parent')
    phone = fields.Char(required=True)
    email = fields.Char()
    is_emergency = fields.Boolean(string='Emergency Contact', default=True)
