from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    umti_student_id = fields.Many2one(
        'school.student', string='Student', index=True,
        compute='_compute_umti_student', store=True, readonly=True)
    umti_course_id = fields.Many2one(
        'umti.course', string='Course',
        related='umti_student_id.course_id', store=True, readonly=True)
    umti_student_state = fields.Selection(
        related='umti_student_id.state', string='Student State',
        store=True, readonly=True)

    @api.depends('partner_id')
    def _compute_umti_student(self):
        Student = self.env['school.student']
        for payment in self:
            payment.umti_student_id = (
                Student.search(
                    [('partner_id', '=', payment.partner_id.id)], limit=1)
                if payment.partner_id else False)
