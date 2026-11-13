from odoo import models, fields, api

class UmtiHostelRoom(models.Model):
    _name = 'umti.hostel.room'
    _description = 'Hostel Room'

    name = fields.Char(string='Room Number/Name', required=True)
    block_id = fields.Many2one('umti.hostel.block', string='Block', ondelete='cascade')
    floor = fields.Char(string='Floor / Level')
    room_type = fields.Selection([
        ('single', 'Single'),
        ('double', 'Double'),
        ('dormitory', 'Dormitory')
    ], string='Room Type', default='double')

    bed_ids = fields.One2many('umti.hostel.bed', 'room_id', string='Beds')
    total_beds = fields.Integer(string='Total Beds', compute='_compute_beds', store=True)
    occupied_beds = fields.Integer(string='Occupied Beds', compute='_compute_beds', store=True)
    available_beds = fields.Integer(string='Available Beds', compute='_compute_beds', store=True)

    @api.depends('bed_ids', 'bed_ids.state')
    def _compute_beds(self):
        for rec in self:
            rec.total_beds = len(rec.bed_ids)
            rec.occupied_beds = len(rec.bed_ids.filtered(lambda b: b.state == 'occupied'))
            rec.available_beds = len(rec.bed_ids.filtered(lambda b: b.state == 'available'))