# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SchoolAdmissionReview(models.Model):
    _name = 'school.admission.review'
    _description = 'Admission Review'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'application_id'
    #TODO: Add tracking
    application_id = fields.Many2one('school.admission.application', string='Application', required=True, ondelete='cascade')
    reviewer_id = fields.Many2one('res.users', string='Reviewer', required=True, ondelete='cascade', default=lambda self: self.env.user.id)
    review_start_date = fields.Date(string='Review Start Date', required=True, default=fields.Date.context_today)
    review_end_date = fields.Date(string='Review End Date')
    state = fields.Selection([
        ('received', 'Received'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('enrolled', 'Enrolled'),
    ], default='received', required=True, tracking=True)

    # Verification and waivers live on the application's document lines, so a
    # review only exposes them for editing; there is nothing to copy around.
    document_ids = fields.One2many(
        related='application_id.document_ids', string='Documents',
        readonly=False)
    requirement_ids = fields.One2many(
        related='application_id.requirement_ids', string='Course Requirements',
        readonly=False)
    general_requirement_ids = fields.One2many(
        related='application_id.general_requirement_ids',
        string='General Requirements', readonly=False,
        domain=[('kind', '=', 'general')])

    # The admission invoice is driven from here now: accept creates it,
    # the review collects the money.
    adm_fee_invoice_id = fields.Many2one(
        related='application_id.adm_fee_invoice_id', string='Admission Invoice',
        readonly=True)
    invoice_count = fields.Integer(related='application_id.invoice_count')
    fee_paid = fields.Boolean(related='application_id.fee_paid')
    fee_status = fields.Selection(
        related='application_id.fee_status', string='Fee Status', readonly=True)
    payment_ids = fields.Many2many(
        'account.payment', string='Payments', compute='_compute_payment_ids')
    payment_count = fields.Integer(compute='_compute_payment_ids')

    @api.depends('adm_fee_invoice_id', 'adm_fee_invoice_id.payment_state')
    def _compute_payment_ids(self):
        """Payments already reconciled against the admission invoice."""
        for record in self:
            invoice = record.adm_fee_invoice_id
            payments = self.env['account.payment']
            if invoice:
                if 'matched_payment_ids' in invoice._fields:
                    payments = invoice.matched_payment_ids
                else:
                    payments = invoice.line_ids.matched_credit_ids.mapped(
                        'credit_move_id.payment_id')
            record.payment_ids = payments
            record.payment_count = len(payments)

    likely_to_reject = fields.Boolean(
        compute='_compute_likely_to_reject', store=True,
        help="A document is missing or a course requirement is unmet, so the "
             "application cannot be accepted as it stands.")
    rejection_hint = fields.Char(compute='_compute_likely_to_reject')

    @api.depends('application_id.document_ids.status',
                 'application_id.requirement_ids.status')
    def _compute_likely_to_reject(self):
        """Flag applications that cannot pass, and say why.

        A document is satisfied by a file or a granted waiver; a requirement
        by being met or waived. Anything still ``missing``/``pending`` — a
        waiver merely requested included, since it has not been granted — is
        a reason the review will end in a rejection.
        """
        for record in self:
            documents = record.document_ids.filtered(
                lambda line: line.status == 'missing')
            requirements = record.requirement_ids.filtered(
                lambda line: line.status == 'pending')
            record.likely_to_reject = bool(documents or requirements)
            parts = []
            if documents:
                parts.append('%d document(s) missing' % len(documents))
            if requirements:
                parts.append('%d requirement(s) unmet' % len(requirements))
            record.rejection_hint = ', '.join(parts)

    reviewer_notes = fields.Text(string='Reviewer Notes')
    rejection_reason = fields.Text(string='Reason for Rejection')

    def action_start_review(self):
        self.application_id.action_start_review()
        self.write({'state': 'under_review'})

    def action_accept(self):
        """Accept once every required document is verified or waived."""
        self.ensure_one()
        pending = self.document_ids.filtered(
            lambda line: not line.attachment and not line.waived)
        if pending:
            raise UserError(_(
                'These documents are still missing: %s',
                ', '.join(pending.mapped('name'))))
        unverified = self.document_ids.filtered(
            lambda line: line.attachment and not line.verified
            and not line.waived)
        if unverified:
            raise UserError(_(
                'These documents must be verified or waived: %s',
                ', '.join(unverified.mapped('name'))))
        self.application_id.action_accept()
        self.write({
            'state': 'accepted',
            'review_end_date': fields.Date.context_today(self),
        })
    
    def action_view_admission_invoice(self):
        """Open the invoice raised when the application was accepted."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Invoice'),
            'res_model': 'account.move',
            'res_id': self.adm_fee_invoice_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    def action_view_payments(self):
        """Open the payment(s) collected for the admission invoice."""
        self.ensure_one()
        payments = self.payment_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Admission Fee Payments'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', payments.ids)],
            'target': 'current',
        }
        if len(payments) == 1:
            action.update({
                'res_id': payments.id,
                'view_mode': 'form',
                'views': [[False, 'form']],
            })
        return action

    def action_open_payment_wizard(self):
        """Ask for the journal to book the admission fee payment in."""
        self.ensure_one()
        if not self.adm_fee_invoice_id:
            raise UserError(_('There is no admission invoice to pay yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'school.admission.payment.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {'default_review_id': self.id},
        }

    def action_enroll(self):
        """Final step: turn the accepted applicant into a student.

        The fee is the only blocker here; the general requirements are on the
        form so the officer can check them off while enrolling, but they do
        not stop it.
        """
        self.ensure_one()
        if self.state != 'accepted':
            raise UserError(_('Accept the application before enrolling it.'))
        application = self.application_id
        if application.admission_fee and not application.fee_paid:
            raise UserError(_('The admission fee has not been paid.'))
        student = application.student_id or self.env['school.student'].search(
            [('application_id', '=', application.id)], limit=1)
        if not student:
            raise UserError(_(
                'No student was created for this application. Accept it '
                'again to recreate the record.'))
        application.write({'student_id': student.id, 'state': 'enrolled'})
        student.action_activate()
        self.write({
            'state': 'enrolled',
            'review_end_date': fields.Date.context_today(self),
        })
        return application.action_open_student()

    def action_reset_draft(self):
        """Send a closed review back to the start.

        The review returns to *Received* and the application goes back to
        *Draft* so the applicant can fix whatever was missing; the rejection
        reason is cleared on both.
        """
        for record in self:
            record.application_id.write({
                'state': 'draft',
                'rejection_reason': False,
            })
            record.write({
                'state': 'received',
                'review_end_date': False,
                'rejection_reason': False,
            })

    def action_reject(self):
        #TODO: Send an email to the user
        if not self.rejection_reason:
            raise UserError(_('Enter a rejection reason first.'))
        self.application_id.action_reject()
        self.application_id.write({'rejection_reason': self.rejection_reason})
        self.write({'state': 'rejected'})
        self.write({'review_end_date': fields.Date.context_today(self)})
    


