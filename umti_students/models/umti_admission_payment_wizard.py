# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SchoolAdmissionPaymentWizard(models.TransientModel):
    """Register the admission fee payment from the review screen.

    The officer only picks a journal: the amount defaults to whatever is still
    due on the invoice and the reconciliation is left to the standard
    ``account.payment.register`` machinery.
    """

    _name = 'school.admission.payment.wizard'
    _description = 'Register Admission Fee Payment'

    review_id = fields.Many2one(
        'school.admission.review', string='Review', required=True,
        ondelete='cascade')
    available_invoice_ids = fields.Many2many(
        'account.move', compute='_compute_available_invoices')
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', required=True,
        domain="[('id', 'in', available_invoice_ids)]")
    partner_id = fields.Many2one(related='invoice_id.partner_id', readonly=True)
    company_id = fields.Many2one(related='invoice_id.company_id', readonly=True)
    currency_id = fields.Many2one(related='invoice_id.currency_id')
    amount = fields.Monetary(
        currency_field='currency_id', required=True,
        help='Defaults to the balance still due on the invoice.')
    journal_id = fields.Many2one(
        'account.journal', string='Payment Journal', required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        help='Journal the payment is booked in.')
    payment_date = fields.Date(
        required=True, default=fields.Date.context_today)

    @api.depends('review_id')
    def _compute_available_invoices(self):
        for wizard in self:
            wizard.available_invoice_ids = (
                wizard.review_id.application_id.intake_invoice_ids)

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.amount = self.invoice_id.amount_residual

    @api.model
    def _default_journal(self):
        return self.env['account.journal'].search([
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        review_id = res.get('review_id') or self.env.context.get(
            'default_review_id')
        if review_id:
            review = self.env['school.admission.review'].browse(review_id)
            invoices = review.application_id.intake_invoice_ids
            invoice = self.env['account.move']
            context_invoice = self.env.context.get('default_invoice_id')
            if context_invoice:
                invoice = invoices.filtered(
                    lambda move: move.id == context_invoice)[:1]
            if not invoice:
                invoice = invoices.filtered(
                    lambda move: move.amount_residual > 0
                    and any(votehead.code == 'ADMISSION'
                            for votehead in
                            move.invoice_line_ids.umti_votehead_id))[:1]
            if not invoice:
                invoice = invoices.filtered(
                    lambda move: move.amount_residual > 0)[:1]
            if not invoice:
                invoice = review.adm_fee_invoice_id or invoices[:1]
            res.setdefault('review_id', review.id)
            if invoice:
                res.setdefault('invoice_id', invoice.id)
                res.setdefault('amount', invoice.amount_residual)
            res.setdefault('journal_id', self._default_journal().id)
        return res

    def action_create_payment(self):
        """Create the payment and reconcile it with the intake invoice."""
        self.ensure_one()
        invoice = self.invoice_id
        if not invoice:
            raise UserError(_('There is no intake invoice to pay.'))
        if invoice.state != 'posted':
            raise UserError(_(
                'The intake invoice must be posted before it is paid.'))
        if invoice.amount_residual <= 0:
            raise UserError(_('The intake invoice is already settled.'))
        register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'journal_id': self.journal_id.id,
            'payment_date': self.payment_date,
            'amount': self.amount or invoice.amount_residual,
        })
        payments = register._create_payments()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payment registered'),
                'message': _(
                    '%(payment)s reconciled with %(invoice)s.',
                    payment=', '.join(payments.mapped('name')) or _('Payment'),
                    invoice=invoice.name,
                ),
                'type': 'success',
                'sticky': False,
                # Re-open the review so ``fee_paid`` reflects the payment.
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Admission Review'),
                    'res_model': 'school.admission.review',
                    'res_id': self.review_id.id,
                    'view_mode': 'form',
                    'views': [[False, 'form']],
                    'target': 'current',
                },
            },
        }
