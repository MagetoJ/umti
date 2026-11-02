from odoo import _, api, fields, models


class UmtiAttendanceSheet(models.Model):
    _inherit = 'umti.attendance.sheet'

    class_schedule_id = fields.Many2one(
        'umti.class.schedule', string='Class Schedule Session',
        tracking=True)
    course_unit_id = fields.Many2one(
        'umti.course.units', string='Scheduled Unit',
        store=True, readonly=True)
    schedule_slot_id = fields.Many2one(
        related='class_schedule_id.slot_id', string='Time Slot')
    schedule_facility_id = fields.Many2one(
        related='class_schedule_id.facility_id', string='Room / Facility')

    @api.onchange('trainer_id')
    def _onchange_trainer_id_schedule(self):
        # A schedule belongs to one trainer; drop it if the trainer changes.
        if (self.class_schedule_id
                and self.class_schedule_id.trainer_id != self.trainer_id):
            self.class_schedule_id = False
            self.course_unit_id = False

    @api.onchange('class_schedule_id')
    def _onchange_class_schedule_id(self):
        if not self.class_schedule_id:
            self.course_unit_id = False
            return
        sched = self.class_schedule_id
        self.course_unit_id = sched.unit_id
        self.course_id = sched.course_id
        self.department_id = sched.department_id
        self.unit_id = sched.unit_id
        self.academic_term_id = sched.academic_term_id
        self.trainer_id = sched.trainer_id
        self._populate_roster()
        if (self.date and sched.day_of_week
                and str(self.date.weekday()) != sched.day_of_week):
            day = sched.day_label
            return {'warning': {
                'title': _("Date does not match the timetable"),
                'message': _(
                    "This session is scheduled on %(day)s but the sheet "
                    "date is %(date)s.", day=day, date=self.date),
            }}

    @api.onchange('unit_id', 'academic_term_id')
    def _onchange_fetch_enrolled_students(self):
        # Roster is driven by the schedule when one is selected.
        if not self.class_schedule_id:
            super()._onchange_fetch_enrolled_students()

    def _get_roster_enrollments(self):
        """With a schedule selected, the roster is the students enrolled in
        that scheduled course/unit/term, whoever is asking. The trainer is the
        one assigned to the session, so ordinary enrollment visibility rules
        must not hide their own class."""
        self.ensure_one()
        sched = self.class_schedule_id
        if sched:
            return self.env['umti.student.unit.enrollment'].sudo().search(
                sched._get_enrollment_domain())
        return super()._get_roster_enrollments()