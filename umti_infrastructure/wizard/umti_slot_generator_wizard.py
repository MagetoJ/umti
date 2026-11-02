from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DAY_SELECTION = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
    ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


class UmtiSlotGeneratorWizard(models.TransientModel):
    _name = 'umti.slot.generator.wizard'
    _description = 'Bulk Time Slot Generator'

    slot_type = fields.Selection([
        ('regular', 'Regular Class Only'),
        ('exam', 'Exam Only'),
        ('both', 'Both (Regular & Exam)'),
    ], string='Slot Type', required=True, default='both')

    # Pre-populated default schedules
    regular_schedule_ids = fields.One2many(
        'umti.slot.generator.schedule', 'wizard_regular_id',
        string='Regular Class Time Slots',
        default=lambda self: self._default_regular_schedules()
    )

    exam_schedule_ids = fields.One2many(
        'umti.slot.generator.schedule', 'wizard_exam_id',
        string='Exam Time Slots',
        default=lambda self: self._default_exam_schedules()
    )

    day_mon = fields.Boolean('Monday', default=True)
    day_tue = fields.Boolean('Tuesday', default=True)
    day_wed = fields.Boolean('Wednesday', default=True)
    day_thu = fields.Boolean('Thursday', default=True)
    day_fri = fields.Boolean('Friday', default=True)
    day_sat = fields.Boolean('Saturday', default=False)
    day_sun = fields.Boolean('Sunday', default=False)

    @api.model
    def _default_regular_schedules(self):
        """Default regular class schedules."""
        return [
            (0, 0, {'name': 'Morning Session 1', 'start_time': 8.0, 'end_time': 11.0}),
            (0, 0, {'name': 'Morning Session 2', 'start_time': 11.0, 'end_time': 14.0}),
            (0, 0, {'name': 'Afternoon Session', 'start_time': 14.0, 'end_time': 17.0}),
        ]

    @api.model
    def _default_exam_schedules(self):
        """Default exam schedules."""
        return [
            (0, 0, {'name': 'Exam Morning Session', 'start_time': 8.5, 'end_time': 11.5}),
            (0, 0, {'name': 'Exam Afternoon Session', 'start_time': 13.5, 'end_time': 16.5}),
        ]

    def _get_selected_days(self):
        mapping = [
            (self.day_mon, '0'), (self.day_tue, '1'), (self.day_wed, '2'),
            (self.day_thu, '3'), (self.day_fri, '4'), (self.day_sat, '5'),
            (self.day_sun, '6'),
        ]
        return [code for selected, code in mapping if selected]

    def _generate_slots_from_schedules(self, selected_days, schedules, stype):
        Slot = self.env['umti.timetable.slot']
        vals_list = []

        for day in selected_days:
            for sched in schedules:
                existing = Slot.search_count([
                    ('day_of_week', '=', day),
                    ('start_time', '=', sched.start_time),
                    ('end_time', '=', sched.end_time),
                    ('slot_type', '=', stype),
                ])
                if not existing:
                    vals_list.append({
                        'day_of_week': day,
                        'start_time': sched.start_time,
                        'end_time': sched.end_time,
                        'slot_type': stype,
                        'name': sched.name,
                    })

        return Slot.create(vals_list)

    def action_generate_slots(self):
        self.ensure_one()
        selected_days = self._get_selected_days()
        if not selected_days:
            raise ValidationError(_("Please select at least one working day."))

        created_slots = self.env['umti.timetable.slot']

        if self.slot_type in ['regular', 'both']:
            if not self.regular_schedule_ids:
                raise ValidationError(_("Please define at least one Regular Class slot schedule."))
            created_slots |= self._generate_slots_from_schedules(
                selected_days, self.regular_schedule_ids, 'regular')

        if self.slot_type in ['exam', 'both']:
            if not self.exam_schedule_ids:
                raise ValidationError(_("Please define at least one Exam slot schedule."))
            created_slots |= self._generate_slots_from_schedules(
                selected_days, self.exam_schedule_ids, 'exam')

        return {
            'type': 'ir.actions.act_window',
            'name': _('Time Slots'),
            'res_model': 'umti.timetable.slot',
            'view_mode': 'list,form',
            'target': 'current',
            'context': {
                'default_slot_type': self.slot_type if self.slot_type != 'both' else 'regular',
                'notification': {
                    'type': 'success',
                    'message': _("%d slot(s) created successfully.") % len(created_slots),
                },
            },
        }


class UmtiSlotGeneratorSchedule(models.TransientModel):
    _name = 'umti.slot.generator.schedule'
    _description = 'Slot Generator Schedule Line'

    wizard_regular_id = fields.Many2one('umti.slot.generator.wizard', ondelete='cascade')
    wizard_exam_id = fields.Many2one('umti.slot.generator.wizard', ondelete='cascade')

    name = fields.Char(string='Slot Name', required=True)
    start_time = fields.Float(string='Start Time', required=True, help="e.g. 8.0 for 08:00")
    end_time = fields.Float(string='End Time', required=True, help="e.g. 11.0 for 11:00")

    @api.constrains('start_time', 'end_time')
    def _check_schedule_times(self):
        for rec in self:
            if not (0 <= rec.start_time < rec.end_time <= 24):
                raise ValidationError(_("Start time must be strictly before end time (0-24)."))