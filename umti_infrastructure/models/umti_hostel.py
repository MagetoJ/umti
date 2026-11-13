# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class UmtiHostel(models.Model):
    _name = 'umti.hostel'
    _description = 'Hostel Facility'

    name = fields.Char(string='Hostel Name', required=True)
    code = fields.Char(string='Hostel Code')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company,
        required=True
    )
    name = fields.Char(string='Hostel Name', required=True)
    code = fields.Char(string='Hostel Code')
    gender_type = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('mixed', 'Mixed')
    ], string='Gender Type', default='mixed')
    
    # Capacity fields referenced by views and dashboard
    capacity = fields.Integer(string='Total Capacity', default=0)
    total_capacity = fields.Integer(string='Total Capacity', default=0)
    occupied_capacity = fields.Integer(string='Occupied Capacity', default=0)
    available_capacity = fields.Integer(string='Available Capacity', compute='_compute_available_capacity', store=True)

    warden_id = fields.Many2one('res.users', string='Warden')
    facility_id = fields.Many2one('umti.facility', string='Campus Facility')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')

    @api.depends('total_capacity', 'occupied_capacity', 'capacity')
    def _compute_available_capacity(self):
        for rec in self:
            tot = rec.total_capacity or rec.capacity or 0
            rec.available_capacity = max(0, tot - (rec.occupied_capacity or 0))

class UmtiHostelBlock(models.Model):
    _name = 'umti.hostel.block'
    _description = 'Campus Hostel Block'
    _order = 'name asc'

    name = fields.Char(string='Hostel Block Name', required=True)
    code = fields.Char(string='Block Code', required=True, index=True)
    gender_restriction = fields.Selection([
        ('male', 'Male Only'),
        ('female', 'Female Only'),
        ('mixed', 'Mixed / Separate Wings')
    ], string='Gender Category', default='male', required=True)

    warden_id = fields.Many2one('res.users', string='Hostel Warden / Supervisor')
    room_ids = fields.One2many('umti.hostel.room', 'hostel_id', string='Rooms')

    total_rooms = fields.Integer(compute='_compute_capacity', store=True)
    total_beds = fields.Integer(compute='_compute_capacity', store=True)
    occupied_beds = fields.Integer(compute='_compute_capacity', store=True)
    available_beds = fields.Integer(compute='_compute_capacity', store=True)

    @api.depends('room_ids.total_beds', 'room_ids.occupied_beds')
    def _compute_capacity(self):
        for block in self:
            block.total_rooms = len(block.room_ids)
            block.total_beds = sum(block.room_ids.mapped('total_beds'))
            block.occupied_beds = sum(block.room_ids.mapped('occupied_beds'))
            block.available_beds = block.total_beds - block.occupied_beds


class UmtiHostelRoom(models.Model):
    _name = 'umti.hostel.room'
    _description = 'Hostel Room'
    _order = 'name asc'

    name = fields.Char(string='Room No / Name', required=True)
    hostel_id = fields.Many2one('umti.hostel.block', string='Hostel Block', required=True, ondelete='cascade')
    floor = fields.Char(string='Floor / Level', default='Ground Floor')
    
    room_type = fields.Selection([
        ('single', 'Single Room (1 Bed)'),
        ('double', 'Double Sharing (2 Beds)'),
        ('quad', 'Quad Sharing (4 Beds)'),
        ('dorm', 'Dormitory (6+ Beds)')
    ], string='Room Type', default='quad', required=True)

    total_beds = fields.Integer(string='Total Beds', default=4, required=True)
    occupied_beds = fields.Integer(compute='_compute_occupancy', store=True)
    available_beds = fields.Integer(compute='_compute_occupancy', store=True)

    bed_ids = fields.One2many('umti.hostel.bed', 'room_id', string='Beds in Room')

    @api.depends('bed_ids.state')
    def _compute_occupancy(self):
        for room in self:
            room.occupied_beds = len(room.bed_ids.filtered(lambda b: b.state == 'occupied'))
            room.available_beds = room.total_beds - room.occupied_beds


class UmtiHostelBed(models.Model):
    _name = 'umti.hostel.bed'
    _description = 'Hostel Bed Slot'
    _order = 'name asc'

    name = fields.Char(string='Bed Label / Code', required=True)
    room_id = fields.Many2one('umti.hostel.room', string='Room', required=True, ondelete='cascade')
    hostel_id = fields.Many2one(related='room_id.hostel_id', string='Hostel Block', store=True)

    state = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance')
    ], string='Status', default='available', tracking=True)

    current_student_id = fields.Many2one('school.student', string='Currently Occupied By', readonly=True)

    @api.depends('room_id', 'name')
    def _compute_display_name(self):
        for bed in self:
            bed.display_name = f"{bed.hostel_id.code}-{bed.room_id.name}-{bed.name}"


class UmtiHostelAllocation(models.Model):
    _name = 'umti.hostel.allocation'
    _description = 'Student Hostel Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Allocation Ref', required=True, default=lambda self: _('New'))
    student_id = fields.Many2one('school.student', string='Student', required=True, tracking=True)
    academic_term_id = fields.Many2one('umti.academic.term', string='Academic Term', required=True, tracking=True)
    
    hostel_id = fields.Many2one('umti.hostel.block', string='Hostel Block', required=True, tracking=True)
    
    # Primary Relational Fields
    room_id = fields.Many2one('umti.hostel.room', string='Room', domain="[('hostel_id', '=', hostel_id)]", required=True)
    bed_id = fields.Many2one('umti.hostel.bed', string='Bed Slot', domain="[('room_id', '=', room_id), ('state', '=', 'available')]", required=True)

    # Dates
    check_in_date = fields.Date(string='Check-In Date')
    check_out_date = fields.Date(string='Check-Out Date')
    check_in = fields.Date(string='Check In Date Alias', related='check_in_date', readonly=False)
    check_out = fields.Date(string='Check Out Date Alias', related='check_out_date', readonly=False)

    # Alias Relational Fields to satisfy view compatibility
    room = fields.Many2one('umti.hostel.room', related='room_id', string='Room Alias', readonly=False)
    bed = fields.Many2one('umti.hostel.bed', related='bed_id', string='Bed Alias', readonly=False)

    state = fields.Selection([
        ('draft', 'Draft / Applied'),
        ('allocated', 'Allocated / Checked-In'),
        ('vacated', 'Vacated / Checked-Out'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('umti.hostel.allocation') or _('New')
        return super().create(vals_list)

    def action_check_in(self):
        for rec in self:
            target_bed = rec.bed_id or rec.bed
            if target_bed and target_bed.state != 'available':
                raise ValidationError(_("Selected Bed %s is already occupied or under maintenance!", target_bed.display_name))
            
            if target_bed:
                target_bed.write({
                    'state': 'occupied',
                    'current_student_id': rec.student_id.id
                })
            rec.write({'state': 'allocated', 'check_in_date': fields.Date.today()})

    def action_check_out(self):
        for rec in self:
            target_bed = rec.bed_id or rec.bed
            if target_bed:
                target_bed.write({
                    'state': 'available',
                    'current_student_id': False
                })
            rec.write({'state': 'vacated', 'check_out_date': fields.Date.today()})
