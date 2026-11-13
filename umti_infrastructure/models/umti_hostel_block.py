# -*- coding: utf-8 -*-
from odoo import models, fields, api

class UmtiHostelBlock(models.Model):
    _name = 'umti.hostel.block'
    _description = 'Hostel Block'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Block Name', required=True, tracking=True)
    code = fields.Char(string='Block Code', required=True, tracking=True)
    description = fields.Text(string='Description / Notes')
    active = fields.Boolean(default=True, tracking=True)
    
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('mixed', 'Mixed')
    ], string='Gender Allocation', required=True, tracking=True)
    
    gender_restriction = fields.Selection(
        related='gender', 
        string='Gender Restriction', 
        readonly=True
    )
    
    warden_id = fields.Many2one('res.users', string='Hostel Warden / Supervisor', tracking=True)

    room_ids = fields.One2many('umti.hostel.room', 'block_id', string='Rooms')
    room_count = fields.Integer(string='Room Count', compute='_compute_room_count')

    total_capacity = fields.Integer(string='Total Capacity', compute='_compute_capacity')
    occupied_capacity = fields.Integer(string='Total Occupied', compute='_compute_capacity')
    available_capacity = fields.Integer(string='Total Available', compute='_compute_capacity')

    @api.depends('room_ids')
    def _compute_room_count(self):
        for record in self:
            record.room_count = len(record.room_ids)

    @api.depends('room_ids', 'room_ids.bed_ids', 'room_ids.bed_ids.state')
    def _compute_capacity(self):
        for record in self:
            beds = record.room_ids.mapped('bed_ids')
            record.total_capacity = len(beds)
            record.occupied_capacity = len(beds.filtered(lambda b: b.state == 'occupied'))
            record.available_capacity = len(beds.filtered(lambda b: b.state == 'available'))

    def action_view_rooms(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("umti_infrastructure.action_umti_hostel_room")
        action['domain'] = [('block_id', '=', self.id)]
        action['context'] = {'default_block_id': self.id}
        return action