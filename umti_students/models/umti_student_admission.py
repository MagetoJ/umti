from odoo import _, fields, models
from odoo.exceptions import UserError


class SchoolStudent(models.Model):
    """Keep a link from the student back to the application it was created from."""
    _inherit = 'school.student'

    application_id = fields.Many2one(
        'school.admission.application', string='Admission Application',
        copy=False, readonly=True, ondelete='set null')
    financial_support_requested = fields.Boolean(
        string='Financial Support Requested', copy=False, readonly=True)
    financial_support_description = fields.Text(
        string='Financial Support Details', copy=False, readonly=True)
    financial_support_attachment_ids = fields.Many2many(
        'ir.attachment', 'school_student_financial_support_rel',
        'student_id', 'attachment_id',
        string='Financial Support Documents', readonly=True)
    admission_fee_waived = fields.Boolean(
        string='Admission Fee Waived', copy=False, readonly=True)

    def action_refund_deposits(self):
        """Credit the refundable voteheads against the intake invoice."""
        self.ensure_one()
        invoice = (self.application_id.refundable_invoice_id
                   or self.application_id.adm_fee_invoice_id)
        if not invoice:
            raise UserError(_('This student has no intake invoice.'))
        refundable = invoice.invoice_line_ids.filtered('umti_refundable')
        if not refundable:
            raise UserError(_(
                'The intake invoice has no refundable voteheads.'))
        already = self.env['account.move.line'].search([
            ('move_id.move_type', '=', 'out_refund'),
            ('move_id.state', '=', 'posted'),
            ('move_id.reversed_entry_id', '=', invoice.id),
            ('umti_votehead_id', 'in',
             refundable.mapped('umti_votehead_id').ids),
        ]).mapped('umti_votehead_id')
        lines = refundable.filtered(
            lambda line: line.umti_votehead_id not in already)
        if not lines:
            raise UserError(_(
                'The refundable voteheads have already been credited.'))
        refund = self.env['account.move'].create({
            'partner_id': invoice.partner_id.id,
            'move_type': 'out_refund',
            'invoice_origin': invoice.name,
            'reversed_entry_id': invoice.id,
            'ref': _('Refund of %(invoice)s', invoice=invoice.name),
            'invoice_line_ids': [(0, 0, {
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'account_id': line.account_id.id,
                'umti_votehead_id': line.umti_votehead_id.id,
                'umti_refundable': True,
            }) for line in lines],
        })
        refund.action_post()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Refund'),
            'res_model': 'account.move',
            'res_id': refund.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }
