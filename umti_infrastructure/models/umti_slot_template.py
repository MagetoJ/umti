from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UmtiTimetableSlotTemplate(models.Model):
    _name = 'umti.timetable.slot.template'
    _description = 'Timetable Slot Template'

    name = fields.Char(string='Template Name', required=True)
    code = fields.Char(string='Code')
    slot_ids = fields.Many2many('umti.timetable.slot', string='Time Slots')
    active = fields.Boolean(default=True)

    # Configurable customizable schedules with built-in default values
    regular_schedule_line_ids = fields.One2many(
        'umti.slot.template.line', 'regular_template_id', 
        string='Regular Class Schedules',
        default=lambda self: self._default_regular_schedules()
    )
    
    exam_schedule_line_ids = fields.One2many(
        'umti.slot.template.line', 'exam_template_id', 
        string='Exam Schedules',
        default=lambda self: self._default_exam_schedules()
    )

    @api.model
    def _default_regular_schedules(self):
        """Default standard regular class schedules."""
        return [
            (0, 0, {'name': 'Morning Session 1', 'start_time': 8.0, 'end_time': 11.0}),
            (0, 0, {'name': 'Morning Session 2', 'start_time': 11.0, 'end_time': 14.0}),
            (0, 0, {'name': 'Afternoon Session', 'start_time': 14.0, 'end_time': 17.0}),
        ]

    @api.model
    def _default_exam_schedules(self):
        """Default standard exam schedules."""
        return [
            (0, 0, {'name': 'Exam Morning Session', 'start_time': 8.5, 'end_time': 11.5}),
            (0, 0, {'name': 'Exam Afternoon Session', 'start_time': 13.5, 'end_time': 16.5}),
        ]

    def _generate_slots_from_lines(self, schedule_lines, slot_type):
        """Helper to create slots from defined schedule lines for Mon-Fri."""
        self.ensure_one()
        if not schedule_lines:
            raise ValidationError(_("No schedule lines configured for %s slots.") % slot_type)

        Slot = self.env['umti.timetable.slot']
        working_days = ['0', '1', '2', '3', '4']  # Monday to Friday
        created_slots = self.env['umti.timetable.slot']

        for day in working_days:
            for line in schedule_lines:
                slot = Slot.search([
                    ('day_of_week', '=', day),
                    ('start_time', '=', line.start_time),
                    ('end_time', '=', line.end_time),
                    ('slot_type', '=', slot_type),
                ], limit=1)

                if not slot:
                    slot = Slot.create({
                        'day_of_week': day,
                        'start_time': line.start_time,
                        'end_time': line.end_time,
                        'slot_type': slot_type,
                        'name': line.name,
                    })
                created_slots |= slot

        self.write({'slot_ids': [(6, 0, (self.slot_ids | created_slots).ids)]})

    def action_generate_regular_slots(self):
        """Generates regular class slots based on configured regular schedules."""
        self._generate_slots_from_lines(self.regular_schedule_line_ids, 'regular')

    def action_generate_exam_slots(self):
        """Generates exam slots based on configured exam schedules."""
        self._generate_slots_from_lines(self.exam_schedule_line_ids, 'exam')

    def action_generate_standard_8to5_slots(self):
        """Generates both regular class and exam slots in bulk."""
        self.action_generate_regular_slots()
        self.action_generate_exam_slots()


class UmtiSlotTemplateLine(models.Model):
    _name = 'umti.slot.template.line'
    _description = 'Slot Template Schedule Line'

    regular_template_id = fields.Many2one('umti.timetable.slot.template', ondelete='cascade')
    exam_template_id = fields.Many2one('umti.timetable.slot.template', ondelete='cascade')
    
    name = fields.Char(string='Slot Label / Name', required=True)
    start_time = fields.Float(string='Start Time', required=True, help="Time in 24h format (e.g. 8.5 for 08:30)")
    end_time = fields.Float(string='End Time', required=True, help="Time in 24h format (e.g. 11.5 for 11:30)")

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if not (0 <= rec.start_time < rec.end_time <= 24):
                raise ValidationError(_("Start time must be before end time (0-24)."))