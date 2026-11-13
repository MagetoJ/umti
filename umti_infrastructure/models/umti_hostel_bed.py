# -*- coding: utf-8 -*-
from odoo import models, fields

class UmtiHostelBed(models.Model):
    _name = 'umti.hostel.bed'
    _description = 'Hostel Bed'

    name = fields.Char(string='Bed Number/Name', required=True)
    room_id = fields.Many2one('umti.hostel.room', string='Room', ondelete='cascade')
    state = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance')
    ], string='Status', default='available')