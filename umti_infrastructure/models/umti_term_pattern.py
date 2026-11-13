# -*- coding: utf-8 -*-
from odoo import models, fields


class UmtiTermPattern(models.Model):
    _inherit = 'umti.term.pattern'

    slot_template_ids = fields.Many2many(
        'umti.timetable.slot.template',
        'umti_term_pattern_slot_template_rel',
        'pattern_id',
        'template_id',
        string='Slot Templates'
    )
