from odoo import fields, models

DAY_SELECTION = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
    ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


class UmtiFacilityUnavailability(models.Model):
    _name = 'umti.facility.unavailability'
    _description = 'Facility Unavailability / Maintenance Window'
    _order = 'facility_id, day_of_week'

    facility_id = fields.Many2one(
        'umti.facility', string='Facility', required=True,
        ondelete='cascade', index=True)
    day_of_week = fields.Selection(
        DAY_SELECTION, string='Day of Week', required=True)
    slot_id = fields.Many2one(
        'umti.timetable.slot', string='Time Slot', required=True,
        ondelete='cascade')
    reason = fields.Char(string='Reason')

    _sql_constraints = [
        ('facility_slot_uniq',
         'unique(facility_id, slot_id)',
         'This facility is already marked unavailable for that slot.'),
    ]
