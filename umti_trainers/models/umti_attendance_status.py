from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UmtiAttendanceStatus(models.Model):
    _name = 'umti.attendance.status'
    _description = 'Attendance Status'
    _order = 'sequence, id'

    name = fields.Char(string='Status', required=True, translate=True)
    code = fields.Char(
        string='Code', required=True,
        help="Short technical code, e.g. present, absent, late.")
    sequence = fields.Integer(default=10)
    is_present = fields.Boolean(
        string='Counts as Present',
        help="Students with this status are counted as present on the sheet; "
             "every other status counts as absent.")
    counts_in_rate = fields.Boolean(
        string='Counts in Attendance Rate', default=True,
        help="Untick for excused absences: they are shown on the record but "
             "do not lower the student's attendance percentage.")
    is_default = fields.Boolean(
        string='Default for New Lines',
        help="Pre-selected for every student when a roster is created.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The status code must be unique.'),
    ]

    @api.constrains('is_default', 'active')
    def _check_single_default(self):
        defaults = self.search_count([('is_default', '=', True)])
        if defaults > 1:
            raise ValidationError(_(
                "Only one attendance status can be the default."))

    @api.model
    def _get_default(self):
        return (self.search([('is_default', '=', True)], limit=1)
                or self.search([], limit=1))
