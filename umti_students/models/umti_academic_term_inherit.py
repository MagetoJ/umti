from odoo import fields, models


class UmtiAcademicTerm(models.Model):
    _inherit = 'umti.academic.term'

    intake_id = fields.Many2one(
        'school.admission.intake', string='Admission Intake', index=True,
        ondelete='set null', tracking=True,
        help="Cohort this term was generated for. Empty for shared or "
             "academic-year terms.")
