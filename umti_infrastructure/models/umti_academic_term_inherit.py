from odoo import fields, models


class UmtiAcademicTermInherit(models.Model):
    _inherit = 'umti.academic.term'

    slot_template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Slot Template',
        help="When set, class and exam schedules for this term will "
             "filter time slots from this template.")
