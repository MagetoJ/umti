from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UmtiExamSchedule(models.Model):
    _name = 'umti.exam.schedule'
    _description = 'Exam Timetable Schedule'
    _order = 'exam_date asc, slot_id asc'

    assessment_id = fields.Many2one('umti.assessment', string='Assessment', required=True, ondelete='cascade')
    exam_date = fields.Date(string='Exam Date', required=True)
    academic_term_id = fields.Many2one('umti.academic.term', string='Academic Term', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    course_id = fields.Many2one('umti.course', string='Course', required=True)
    course_unit_ids = fields.Many2many('umti.course.units', related='course_id.unit_ids', string='Course Units')
    department_id = fields.Many2one('hr.department', string='Department')
    level_id = fields.Many2one('umti.course.level', string='Level')
    unit_id = fields.Many2one('umti.course.units', string='Unit', domain="[('id', 'in', course_unit_ids)]")

    facility_id = fields.Many2one('umti.facility', string='Exam Hall', required=True)
    slot_id = fields.Many2one(
        'umti.timetable.slot', 
        string='Time Slot', 
        required=True, 
        domain="[('slot_type', 'in', ['exam', 'both'])]"
    )
    invigilator_id = fields.Many2one('hr.employee', string='Invigilator')

    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('published', 'Published'),
    ], default='draft', required=True)

    # ------------------------------------------------------------ Onchange Logic
    @api.onchange('assessment_id')
    def _onchange_assessment_id(self):
        if self.assessment_id:
            self.course_id = self.assessment_id.course_id
            self.academic_term_id = self.assessment_id.semester_id
            self.level_id = self.assessment_id.level_id
            
            if self.assessment_id.course_id and hasattr(self.assessment_id.course_id, 'department_id'):
                self.department_id = self.assessment_id.course_id.department_id
                
            # If primary unit is set, attempt to get its specific date from the schedule matrix
            target_date = False
            if self.assessment_id.unit_id:
                self.unit_id = self.assessment_id.unit_id
                unit_line = self.assessment_id.unit_schedule_ids.filtered(lambda l: l.unit_id == self.unit_id)
                if unit_line and unit_line.date:
                    target_date = unit_line.date

            # Fall back to general assessment date or first scheduled unit date or today
            if not target_date:
                first_scheduled_unit = self.assessment_id.unit_schedule_ids.filtered(lambda l: l.date)
                if first_scheduled_unit:
                    target_date = first_scheduled_unit[0].date
                    if not self.unit_id:
                        self.unit_id = first_scheduled_unit[0].unit_id
                else:
                    target_date = self.assessment_id.date or fields.Date.today()

            self.exam_date = target_date
            self._auto_select_time_slot()
        else:
            self.course_id = False
            self.academic_term_id = False
            self.level_id = False
            self.department_id = False
            self.unit_id = False
            self.exam_date = False
            self.slot_id = False

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.assessment_id and self.unit_id:
            unit_line = self.assessment_id.unit_schedule_ids.filtered(lambda l: l.unit_id == self.unit_id)
            if unit_line and unit_line.date:
                self.exam_date = unit_line.date
                self._auto_select_time_slot()

    @api.onchange('exam_date')
    def _onchange_exam_date(self):
        if self.exam_date:
            self._auto_select_time_slot()

    def _auto_select_time_slot(self):
        if self.exam_date:
            weekday_str = str(self.exam_date.weekday())
            slot = self.env['umti.timetable.slot'].search([
                ('day_of_week', '=', weekday_str),
                ('slot_type', 'in', ['exam', 'both'])
            ], limit=1)
            if slot:
                self.slot_id = slot

    # -------------------------------------------------- Operational Conflict Engine
    @api.constrains('facility_id', 'exam_date', 'slot_id')
    def _check_facility_conflict(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('facility_id', '=', rec.facility_id.id),
                ('exam_date', '=', rec.exam_date),
                ('slot_id', '=', rec.slot_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    "Facility Conflict: Hall '%s' is already booked for another exam on %s during slot '%s'."
                ) % (rec.facility_id.display_name, rec.exam_date, rec.slot_id.display_name))

    @api.constrains('invigilator_id', 'exam_date', 'slot_id')
    def _check_invigilator_conflict(self):
        for rec in self.filtered('invigilator_id'):
            domain = [
                ('id', '!=', rec.id),
                ('invigilator_id', '=', rec.invigilator_id.id),
                ('exam_date', '=', rec.exam_date),
                ('slot_id', '=', rec.slot_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    "Invigilator Conflict: '%s' is already assigned to supervise another exam on %s during slot '%s'."
                ) % (rec.invigilator_id.display_name, rec.exam_date, rec.slot_id.display_name))

    @api.constrains('course_id', 'level_id', 'exam_date', 'slot_id')
    def _check_student_group_conflict(self):
        for rec in self.filtered(lambda r: r.course_id and r.level_id):
            domain = [
                ('id', '!=', rec.id),
                ('course_id', '=', rec.course_id.id),
                ('level_id', '=', rec.level_id.id),
                ('exam_date', '=', rec.exam_date),
                ('slot_id', '=', rec.slot_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    "Student Schedule Collision: Course '%s' (Level '%s') already has an exam scheduled on %s during slot '%s'."
                ) % (rec.course_id.display_name, rec.level_id.display_name, rec.exam_date, rec.slot_id.display_name))

    # ------------------------------------------------------------ Action Handlers
    def action_confirm(self):
        self.write({'status': 'confirmed'})

    def action_publish(self):
        self.write({'status': 'published'})

    def action_reset_draft(self):
        self.write({'status': 'draft'})