# -*- coding: utf-8 -*-
from odoo import fields, models, _


class UmtiLibraryBooks(models.Model):
    _name = 'umti.library.books'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'title'

    title = fields.Char(string='Title', required=True, tracking=True)
    internal_reference = fields.Char(string='Internal Reference', required=True, tracking=True)
    genre_id = fields.Many2one('umti.library.book.genre', string='Genre', required=True, tracking=True)
    author_id = fields.Many2one('umti.library.book.author', string='Author', required=True, tracking=True)
    publisher_id = fields.Many2one('umti.library.book.publisher', string='Publisher', required=True, tracking=True)
    isbn = fields.Char(string='ISBN', tracking=True)
    bar_code = fields.Char(string='Bar Code', tracking=True)
    edition = fields.Char(string='Edition', required=True, tracking=True)
    year = fields.Integer(string='Year', tracking=True)
    pages = fields.Integer(string='Pages', tracking=True)
    description = fields.Text(string='Description', tracking=True)
    date_acquired = fields.Date(string='Date Acquired', default=fields.Date.context_today, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', tracking=True, default=lambda self: self.env.company.currency_id)
    purchase_price = fields.Monetary(string='Purchase Price', tracking=True, currency_field='currency_id')
    daily_overdue_charge = fields.Monetary(string='Daily Overdue Charge', tracking=True, currency_field='currency_id', default=20)
    lending_counts = fields.Integer(string='Lending Counts', compute='_compute_lending_counts')

    status = fields.Selection([
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
        ('lost', 'Lost'),
    ], string='Status', tracking=True, default='available')

    def _compute_lending_counts(self):
        self.lending_counts = self.env['umti.library.lending'].search_count([('book_id', '=', self.id)])


    def view_all_lendings(self):
        self.ensure_one()
        return {
            'name': _('Lendings'),
            'view_mode': 'list,form',
            'res_model': 'umti.library.lending',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': [('book_id', '=', self.id)],
            'context': {'default_book_id': self.id}, 
        }

class BookGenre(models.Model):
    _name = 'umti.library.book.genre'
    _description = 'Umti Library Book Genre'

    name = fields.Char(string='Name', required=True)

class BookAuthor(models.Model):
    _name = 'umti.library.book.author'
    _description = 'Umti Library Book Author'

    name = fields.Char(string='Name', required=True)

class BookPublisher(models.Model):
    _name = 'umti.library.book.publisher'
    _description = 'Umti Library Book Publisher'

    name = fields.Char(string='Name', required=True)