from odoo import fields, models


class SchoolStudent(models.Model):
    """Keep a link from the student back to the application it was created from."""
    _inherit = 'school.student'

    application_id = fields.Many2one(
        'school.admission.application', string='Admission Application',
        copy=False, readonly=True, ondelete='set null')
