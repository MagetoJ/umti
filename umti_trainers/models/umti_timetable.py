# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class UmtiTimetableSlot(models.Model):
    _name = 'umti.timetable.slot'
    _description = 'Master Timetable Time Slot'
    _order = 'day_of_week asc, start_time asc'

    name = fields.Char(string='Slot Label', compute='_compute_name', store=True)
    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
    ], string='Day of Week', required=True, default='0')

    start_time = fields.Float(string='Start Time (24h)', required=True, help="e.g. 8.5 for 08:30 AM")
    end_time = fields.Float(string='End Time (24h)', required=True, help="e.g. 11.5 for 11:30 AM")

    slot_type = fields.Selection([
        ('lecture', 'Lecture / Theory'),
        ('lab', 'Practical Lab / Workshop'),
        ('break', 'Tea / Lunch Break'),
    ], string='Slot Type', default='lecture', required=True)

    active = fields.Boolean(default=True)

    @api.depends('day_of_week', 'start_time', 'end_time')
    def _compute_name(self):
        days = dict(self._fields['day_of_week'].selection)
        for rec in self:
            day_str = days.get(rec.day_of_week, '')
            start_str = f"{int(rec.start_time):02d}:{int((rec.start_time % 1) * 60):02d}"
            end_str = f"{int(rec.end_time):02d}:{int((rec.end_time % 1) * 60):02d}"
            rec.name = f"{day_str} ({start_str} - {end_str})"

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if rec.start_time >= rec.end_time:
                raise ValidationError(_("Start time must be strictly earlier than end time."))


class UmtiTimetable(models.Model):
    _name = 'umti.timetable'
    _description = 'Class Group Timetable Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Timetable Title', required=True, tracking=True)
    academic_term_id = fields.Many2one('umti.academic.term', string='Academic Term', required=True, tracking=True)
    class_group_id = fields.Many2one('umti.class.group', string='Class Group / Cohort', required=True, tracking=True)
    department_id = fields.Many2one(related='class_group_id.department_id', string='Department', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True)

    session_ids = fields.One2many('umti.timetable.session', 'timetable_id', string='Scheduled Sessions')

    def action_generate_timetable(self):
        """
        Automated Engine: Matches allocated Unit Trainers to Class Groups across available Slots & Rooms.
        """
        self.ensure_one()
        SessionObj = self.env['umti.timetable.session']
        SlotObj = self.env['umti.timetable.slot']
        AllocationObj = self.env['umti.trainer.allocation']
        RoomObj = self.env['umti.room'] if 'umti.room' in self.env else False

        # Clear existing draft sessions
        self.session_ids.filtered(lambda s: self.state == 'draft').unlink()

        # Fetch allocations for this class group or department
        allocations = AllocationObj.search([
            ('academic_term_id', '=', self.academic_term_id.id),
            '|',
            ('class_group_id', '=', self.class_group_id.id),
            ('department_id', '=', self.department_id.id)
        ])

        if not allocations:
            raise UserError(_("No Trainer Allocations found for Class Group %s in this term.", self.class_group_id.name))

        slots = SlotObj.search([('active', '=', True), ('slot_type', '!=', 'break')])
        available_rooms = RoomObj.search([('active', '=', True)]) if RoomObj else False

        created_sessions = self.env['umti.timetable.session']
        slot_idx = 0

        for alloc in allocations:
            # Schedule weekly sessions based on required hours/weekly slots
            weekly_slots_needed = getattr(alloc, 'weekly_slots', 2)

            for _ in range(weekly_slots_needed):
                if slot_idx >= len(slots):
                    break  # All available slots filled for the week

                assigned_slot = slots[slot_idx]
                slot_idx += 1

                # Find available room without double-booking
                assigned_room = False
                if available_rooms:
                    for room in available_rooms:
                        conflict = SessionObj.search([
                            ('slot_id', '=', assigned_slot.id),
                            ('room_id', '=', room.id),
                            ('timetable_id.academic_term_id', '=', self.academic_term_id.id)
                        ], limit=1)
                        if not conflict:
                            assigned_room = room
                            break

                # Create Session record
                session = SessionObj.create({
                    'timetable_id': self.id,
                    'class_group_id': self.class_group_id.id,
                    'slot_id': assigned_slot.id,
                    'unit_id': alloc.unit_id.id if hasattr(alloc, 'unit_id') else False,
                    'trainer_id': alloc.trainer_id.id if hasattr(alloc, 'trainer_id') else False,
                    'room_id': assigned_room.id if assigned_room else False,
                })
                created_sessions |= session

        self.write({'state': 'published'})
        return True


class UmtiTimetableSession(models.Model):
    _name = 'umti.timetable.session'
    _description = 'Individual Timetable Session Slot'
    _order = 'slot_id asc'

    timetable_id = fields.Many2one('umti.timetable', string='Timetable', required=True, ondelete='cascade')
    class_group_id = fields.Many2one(related='timetable_id.class_group_id', string='Class Group', store=True)
    slot_id = fields.Many2one('umti.timetable.slot', string='Time Slot', required=True)
    
    unit_id = fields.Many2one('umti.course.units', string='Course Unit', required=True)
    trainer_id = fields.Many2one('res.users', string='Assigned Trainer', required=True)
    room_id = fields.Many2one('umti.room', string='Assigned Room / Workshop')

    @api.constrains('slot_id', 'trainer_id', 'room_id', 'timetable_id')
    def _check_timetable_conflicts(self):
        for rec in self:
            term_id = rec.timetable_id.academic_term_id.id

            # 1. Trainer Conflict Check
            if rec.trainer_id and rec.slot_id:
                trainer_conflict = self.search([
                    ('id', '!=', rec.id),
                    ('slot_id', '=', rec.slot_id.id),
                    ('trainer_id', '=', rec.trainer_id.id),
                    ('timetable_id.academic_term_id', '=', term_id)
                ], limit=1)
                if trainer_conflict:
                    raise ValidationError(_(
                        "Trainer Collision: %s is already scheduled for another class during slot %s!",
                        rec.trainer_id.name, rec.slot_id.name
                    ))

            # 2. Room Conflict Check
            if rec.room_id and rec.slot_id:
                room_conflict = self.search([
                    ('id', '!=', rec.id),
                    ('slot_id', '=', rec.slot_id.id),
                    ('room_id', '=', rec.room_id.id),
                    ('timetable_id.academic_term_id', '=', term_id)
                ], limit=1)
                if room_conflict:
                    raise ValidationError(_(
                        "Room Collision: %s is already occupied during slot %s!",
                        rec.room_id.name, rec.slot_id.name
                    ))
