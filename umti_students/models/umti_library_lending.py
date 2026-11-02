# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class UmtiLibraryLending(models.Model):
    _name = 'umti.library.lending'
    _rec_name = 'student_id'
    _description = 'Umti Library Lending'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    #TODO: Add tracking
    #TODO: REC NAME to have ISBN or BARCODE
    #TODO: Readonly states

    student_id = fields.Many2one('school.student', string='Student', required=True, domain=[('state', '=', 'active')], ondelete='cascade', index=True)
    book_id = fields.Many2one('umti.library.books', string='Book', required=True, domain="[('status', '=', 'available')]", ondelete='cascade', index=True)
    borrow_date = fields.Date(string='Borrow Date', required=True, default=fields.Date.context_today)
    return_date = fields.Date(string='Actual Return Date', required=True,)
    due_date = fields.Date(string='Due Date', default = lambda self: fields.Date.context_today(self) + timedelta(days=14))
    is_overdue = fields.Boolean(compute='_compute_is_overdue')
    overdue_days = fields.Integer(compute='_compute_is_overdue')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('leased', 'Leased'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
        ('lost', 'Lost'),
    ], string='Status', required=True, default='draft')
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    invoice_payment_state = fields.Selection(string="Repayment State", related='invoice_id.payment_state')
    overdue_charge_id = fields.Many2one('account.move', string='Overdue Charges', readonly=True)
    overdue_payment_state = fields.Selection(string="Fine Payment State" , related='overdue_charge_id.payment_state')
    currency_id = fields.Many2one('res.currency', string='Currency', tracking=True, default=lambda self: self.env.company.currency_id)
    overdue_charge_amount = fields.Monetary(string='Overdue Charge Amount', compute='_compute_is_overdue', currency_field='currency_id')
    issued_by = fields.Many2one('res.users', string='Issued By', tracking=True, default=lambda self: self.env.user)

    @api.constrains('due_date', 'return_date')
    def _check_dates(self):
        for rec in self:
            if rec.due_date and rec.return_date and rec.due_date > rec.return_date:
                raise ValidationError(_('Due Date cannot be after Return Date.'))

    @api.depends('due_date', 'return_date')
    def _compute_is_overdue(self):
        for rec in self:
            rec.is_overdue = rec.due_date and rec.return_date and rec.due_date < rec.return_date
            rec.overdue_days = rec.due_date and rec.return_date and (rec.return_date - rec.due_date).days if rec.is_overdue else 0
            rec.overdue_charge_amount = rec.book_id.daily_overdue_charge* abs(rec.overdue_days) if rec.is_overdue else 0
        #TODO: AComputaion of overdue logic

        
    @api.onchange('borrow_date')
    def _onchange_borrow_date(self):
        if self.borrow_date:
            self.due_date = self.borrow_date + timedelta(days=14)

    def action_lease(self):
        self.book_id.write({'status': 'unavailable'})
        self.write({'state': 'leased'})
    


    def action_return(self):
        if self.is_overdue:
            if self.book_id.daily_overdue_charge:
                overdue_name = f"Overdue Charge Fee: {self.book_id.title}: {self.overdue_days} Days"
                overdue_charge = self.env['account.move'].create({
                    'partner_id': self.student_id.partner_id.id,
                    'date': fields.Date.context_today(self),
                    'move_type': 'out_invoice',
                    'company_id': self.env.company.id,
                    'ref': overdue_name,
                    'invoice_line_ids': [(0, 0, {
                        'name': overdue_name,
                        'quantity': 1,
                        'price_unit': abs(self.book_id.daily_overdue_charge)* abs(self.overdue_days),
                    })],
                })
                overdue_charge.action_post()
                self.overdue_charge_id = overdue_charge.id
        self.book_id.write({'status': 'available'})
        self.write({'state': 'returned'})

    def action_lost(self):
        #invoice the student for the lost book
        book_name = f"Lost Book Fee: {self.book_id.title}"
        invoice = self.env['account.move'].create({
            'partner_id': self.student_id.partner_id.id,
            'date': fields.Date.context_today(self),
            'move_type': 'out_invoice',
            'company_id': self.env.company.id,
            'ref': book_name,
            'invoice_line_ids': [(0, 0, {
                'name': book_name,
                'quantity': 1,
                'price_unit': self.book_id.purchase_price,
            })],
        })
        invoice.action_post()
        self.invoice_id = invoice.id
        self.write({'state': 'lost'})
        self.book_id.write({'status': 'lost'})
