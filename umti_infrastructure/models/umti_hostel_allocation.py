# -*- coding: utf-8 -*-
from odoo import api, fields, models


class UmtiHostelAllocation(models.Model):
    """Extends the allocation defined in umti_students.

    umti_students owns this model (student, hostel, state, fee, ...).
    This module only adds a link to the physical block / room / bed.
    It must use _inherit (no _name): redefining the model here would
    replace the umti_students version and drop its fields.
    """
    _inherit = 'umti.hostel.allocation'

    block_id = fields.Many2one(
        'umti.hostel.block', string='Hostel Block', tracking=True)
    room_id = fields.Many2one(
        'umti.hostel.room', string='Room (Inventory)',
        domain="[('block_id', '=', block_id)]", tracking=True)
    bed_id = fields.Many2one(
        'umti.hostel.bed', string='Bed (Inventory)',
        domain="[('room_id', '=', room_id), ('state', '=', 'available')]",
        tracking=True)

    @api.onchange('block_id')
    def _onchange_block_id(self):
        if self.room_id and self.room_id.block_id != self.block_id:
            self.room_id = False
            self.bed_id = False

    @api.onchange('room_id')
    def _onchange_room_id(self):
        if self.room_id:
            self.room = self.room_id.name
        if self.bed_id and self.bed_id.room_id != self.room_id:
            self.bed_id = False

    @api.onchange('bed_id')
    def _onchange_bed_id(self):
        if self.bed_id:
            self.bed = self.bed_id.name

    def action_check_in(self):
        res = super().action_check_in()
        self.mapped('bed_id').write({'state': 'occupied'})
        return res

    def action_check_out(self):
        res = super().action_check_out()
        self.mapped('bed_id').write({'state': 'available'})
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self.filtered(lambda a: a.state == 'cancelled').mapped('bed_id') \
            .filtered(lambda b: b.state == 'occupied') \
            .write({'state': 'available'})
        return res
