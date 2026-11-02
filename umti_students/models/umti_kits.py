# -*- coding: utf-8 -*-
from odoo import fields, models, _


class UmtiKits(models.Model):
    _name = 'umti.kits'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    internal_reference = fields.Char(string='Internal Reference', required=True, tracking=True)
    related_product = fields.Many2one('product.product', string='Related Product', tracking=True)
    description = fields.Text(string='Description', tracking=True)
    date_acquired = fields.Date(string='Date Acquired', default=fields.Date.context_today, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', tracking=True, default=lambda self: self.env.company.currency_id)
    purchase_price = fields.Monetary(string='Purchase Price', tracking=True, currency_field='currency_id')    
    lending_counts = fields.Integer(string='Lending Counts', compute='_compute_lending_counts')

    status = fields.Selection([
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
        ('lost', 'Lost'),
    ], string='Status', tracking=True, default='available')

    def _compute_lending_counts(self):
        self.lending_counts = self.env['umti.kit.issuance'].search_count([('kit_id', '=', self.id)])


    def view_all_lendings(self):
        self.ensure_one()
        return {
            'name': _('Lendings'),
            'view_mode': 'list,form',
            'res_model': 'umti.kit.issuance',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': [('kit_id', '=', self.id)],
            'context': {'default_kit_id': self.id}, 
        }


