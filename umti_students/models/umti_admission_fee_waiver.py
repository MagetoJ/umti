from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SchoolAdmissionFeeWaiverWizard(models.TransientModel):
    """Record a deliberate decision to accept without an admission fee."""

    _name = 'school.admission.fee.waiver.wizard'
    _description = 'Waive Admission Fee'

    review_id = fields.Many2one(
        'school.admission.review', required=True, ondelete='cascade')
    application_id = fields.Many2one(
        related='review_id.application_id', readonly=True)
    applicant_name = fields.Char(
        related='application_id.applicant_name', readonly=True)
    admission_fee = fields.Monetary(
        related='application_id.admission_fee',
        currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(
        related='application_id.currency_id', readonly=True)
    apply_financial_support = fields.Boolean(
        related='application_id.apply_financial_support', readonly=True)
    financial_support_description = fields.Text(
        related='application_id.financial_support_description',
        readonly=True)
    financial_support_attachment_ids = fields.Many2many(
        'ir.attachment', compute='_compute_financial_support_attachments')
    reason = fields.Text(required=True)

    @api.depends('application_id.financial_support_attachment_ids')
    def _compute_financial_support_attachments(self):
        for wizard in self:
            wizard.financial_support_attachment_ids = (
                wizard.application_id.financial_support_attachment_ids)

    def action_confirm(self):
        self.ensure_one()
        application = self.application_id
        invoice = application.adm_fee_invoice_id
        if invoice and invoice.state != 'cancel':
            raise UserError(_(
                'An admission invoice already exists for this application. '
                'Cancel it before waiving the fee.'))
        application.write({
            'admission_fee_waived': True,
            'admission_fee_waiver_reason': self.reason,
            'admission_fee_waived_by': self.env.user.id,
            'admission_fee_waived_date': fields.Date.context_today(self),
        })
        application.message_post(body=_(
            "Admission fee waived by %(user)s: %(reason)s",
            user=self.env.user.name, reason=self.reason))
        return {'type': 'ir.actions.act_window_close'}
