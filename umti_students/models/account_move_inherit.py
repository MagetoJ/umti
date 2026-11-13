from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    umti_student_id = fields.Many2one(
        'school.student', string='Student', index=True, copy=False)
    umti_academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', index=True, copy=False)
    umti_fee_period_sequence = fields.Integer(
        string='Fee Period', copy=False,
        help="Pattern sequence of the billed period (10, 20, ...).")
    umti_invoice_kind = fields.Selection([
        ('intake', 'Intake'),
        ('semester', 'Semester'),
    ], string='Student Invoice Type', index=True, copy=False)
    umti_course_id = fields.Many2one(
        'umti.course', string='Course',
        related='umti_student_id.course_id', store=True, readonly=True)
    umti_academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year',
        related='umti_academic_term_id.academic_year_id', store=True,
        readonly=True)
    umti_student_state = fields.Selection(
        related='umti_student_id.state', string='Student State',
        store=True, readonly=True)
