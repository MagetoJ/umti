from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UmtiFacility(models.Model):
    _name = 'umti.facility'
    _description = 'Campus Facility / Room'
    _order = 'building_name, code'

    name = fields.Char(string='Room Name', required=True)
    code = fields.Char(string='Room Code', required=True)
    building_name = fields.Char(string='Building')
    floor_level = fields.Char(string='Floor / Level')
    department_id = fields.Many2one('umti.department', string='Department')
    facility_type = fields.Selection([
        ('classroom', 'Classroom'),
        ('lecture_hall', 'Lecture Hall'),
        ('lab', 'Laboratory'),
        ('computer_lab', 'Computer Lab'),
        ('workshop', 'Workshop'),
        ('exam_hall', 'Exam Hall'),
        ('library', 'Library'),
        ('office', 'Office'),
        ('other', 'Other'),
    ], string='Type', default='classroom', required=True)
    capacity = fields.Integer(string='Capacity', default=30, required=True)
    status = fields.Selection([
        ('available', 'Available'),
        ('maintenance', 'Under Maintenance'),
        ('reserved', 'Reserved'),
        ('decommissioned', 'Decommissioned'),
    ], string='Status', default='available', required=True)
    equipment_ids = fields.One2many(
        'umti.facility.equipment', 'facility_id', string='Equipment')
    unavailability_ids = fields.One2many(
        'umti.facility.unavailability', 'facility_id',
        string='Unavailability Windows')
    remarks = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'The room code must be unique per company.'),
    ]

    @api.depends('name', 'code', 'building_name')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.code:
                parts.append('[%s]' % rec.code)
            if rec.name:
                parts.append(rec.name)
            if rec.building_name:
                parts.append('(%s)' % rec.building_name)
            rec.display_name = ' '.join(parts) or rec.name or ''

    @api.constrains('capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.capacity <= 0:
                raise ValidationError(_("Room capacity must be greater than zero."))


class UmtiFacilityEquipment(models.Model):
    _name = 'umti.facility.equipment'
    _description = 'Facility Equipment'

    facility_id = fields.Many2one(
        'umti.facility', string='Facility', required=True, ondelete='cascade')
    name = fields.Char(string='Equipment Name', required=True)
    serial_number = fields.Char(string='Serial Number')
    quantity = fields.Integer(string='Quantity', default=1)
    condition = fields.Selection([
        ('functional', 'Functional'),
        ('repair_needed', 'Repair Needed'),
        ('broken', 'Broken'),
    ], string='Condition', default='functional', required=True)
    remarks = fields.Char()
