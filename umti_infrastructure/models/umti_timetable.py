from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools import format_date

DAY_SELECTION = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
    ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


class UmtiTimetableSlot(models.Model):
    _name = 'umti.timetable.slot'
    _description = 'Timetable Time Slot'
    _order = 'day_of_week, start_time'

    day_of_week = fields.Selection(DAY_SELECTION, string='Day', required=True)
    start_time = fields.Float(string='Start Time', required=True)
    end_time = fields.Float(string='End Time', required=True)
    slot_type = fields.Selection([
        ('regular', 'Regular Class'),
        ('exam', 'Exam Only'),
        ('both', 'Both'),
    ], string='Slot Type', default='regular', required=True)
    template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Slot Template',
        ondelete='set null', index=True)
    color = fields.Integer(compute='_compute_color', store=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('slot_type')
    def _compute_color(self):
        color_map = {'regular': 4, 'exam': 2, 'both': 10}
        for rec in self:
            rec.color = color_map.get(rec.slot_type, 0)

    @api.depends('day_of_week', 'start_time', 'end_time')
    def _compute_display_name(self):
        day_map = dict(DAY_SELECTION)
        for rec in self:
            day = day_map.get(rec.day_of_week, '')
            sh, sm = divmod(int(rec.start_time * 60), 60)
            eh, em = divmod(int(rec.end_time * 60), 60)
            rec.display_name = '%s %02d:%02d–%02d:%02d' % (day, sh, sm, eh, em)

    # ---- Requirement 2: Time Range Integrity ----
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if not (0 <= rec.start_time < rec.end_time <= 24):
                raise ValidationError(
                    _("Times must satisfy 0 <= start < end <= 24."))

    # ---- Requirement 2: Strict Overlap Constraint ----
    @api.constrains('day_of_week', 'start_time', 'end_time', 'slot_type')
    def _check_overlap(self):
        for rec in self:
            overlapping = self.search([
                ('id', '!=', rec.id),
                ('day_of_week', '=', rec.day_of_week),
                ('start_time', '<', rec.end_time),
                ('end_time', '>', rec.start_time),
            ])
            for other in overlapping:
                if (rec.slot_type == other.slot_type
                        or rec.slot_type == 'both'
                        or other.slot_type == 'both'):
                    day_label = dict(DAY_SELECTION).get(rec.day_of_week, '')
                    raise ValidationError(_(
                        "Slot overlap on %(day)s: "
                        "%(new)s conflicts with %(existing)s.",
                        day=day_label,
                        new=rec.display_name,
                        existing=other.display_name,
                    ))


class UmtiClassSchedule(models.Model):
    _name = 'umti.class.schedule'
    _description = 'Class Schedule Entry'
    _order = 'academic_term_id, day_of_week, start_time'
    _rec_names_search = ['unit_id', 'facility_id', 'course_id']

    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True,
        domain="[('status', '=', 'in_progress')]")
    course_id = fields.Many2one(
        'umti.course', string='Course', required=True)
    department_id = fields.Many2one(
        related='course_id.department_id', store=True, string='Department')
    level_id = fields.Many2one('umti.course.level', string='Level')
    course_unit_ids = fields.Many2many(
        'umti.course.units', related='course_id.unit_ids',
        string='Course Units')
    unit_id = fields.Many2one(
        'umti.course.units', string='Unit', required=True,
        domain="[('id', 'in', course_unit_ids)]")
    trainer_id = fields.Many2one(
        'res.users', string='Trainer', required=True,
        domain="['|', ('share', '=', False), ('id', 'in', trainer_user_ids)]")
    trainer_user_ids = fields.Many2many(
        'res.users', string='Selectable Trainers',
        compute='_compute_trainer_user_ids',
        help="Portal users linked to an employee holding an active trainer "
             "allocation. Used to relax the trainer picker domain.")
    facility_id = fields.Many2one(
        'umti.facility', string='Room / Facility', required=True,
        domain="[('status', '=', 'available')]")
    slot_id = fields.Many2one(
        'umti.timetable.slot', string='Time Slot', required=True,
        domain="[('slot_type', 'in', ['regular', 'both'])]")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    # Slot details surfaced on the schedule itself so every list, picker,
    # student/trainer tab and portal page can show *when* the class is.
    day_of_week = fields.Selection(
        related='slot_id.day_of_week', store=True,
        string='Day')
    start_time = fields.Float(
        related='slot_id.start_time', store=True, string='Start')
    end_time = fields.Float(
        related='slot_id.end_time', store=True, string='End')
    student_count = fields.Integer(
        compute='_compute_student_count', string='Enrolled Students')
    day_label = fields.Char(compute='_compute_slot_labels', string='Day Name')
    time_range = fields.Char(compute='_compute_slot_labels', string='Time')

    @api.depends('slot_id.day_of_week', 'slot_id.start_time',
                 'slot_id.end_time')
    def _compute_slot_labels(self):
        day_map = dict(DAY_SELECTION)
        for rec in self:
            slot = rec.slot_id
            rec.day_label = day_map.get(slot.day_of_week, '') if slot else ''
            if slot:
                sh, sm = divmod(int(round(slot.start_time * 60)), 60)
                eh, em = divmod(int(round(slot.end_time * 60)), 60)
                rec.time_range = '%02d:%02d–%02d:%02d' % (sh, sm, eh, em)
            else:
                rec.time_range = ''

    @api.depends('unit_id.name', 'slot_id.display_name',
                 'facility_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.unit_id.name, rec.slot_id.display_name,
                     rec.facility_id.display_name]
            rec.display_name = ' | '.join(p for p in parts if p) or _('New')

    @api.depends('unit_id', 'academic_term_id')
    def _compute_trainer_user_ids(self):
        """Portal trainers stay selectable: the picker offers whoever the
        department assigned to the unit for the term, plus internal users."""
        Mapping = self.env['umti.unit.trainer'].sudo()
        Users = self.env['res.users']
        for rec in self:
            users = Users
            if rec.unit_id and rec.academic_term_id:
                mapping = Mapping.search([
                    ('unit_id', '=', rec.unit_id.id),
                    ('academic_term_id', '=', rec.academic_term_id.id),
                    ('active', '=', True),
                ], limit=1)
                users = mapping.trainer_id.user_id
            rec.trainer_user_ids = users

    def _get_enrollment_domain(self):
        self.ensure_one()
        return [
            ('unit_id', '=', self.unit_id.id),
            ('academic_term_id', '=', self.academic_term_id.id),
            ('course_id', '=', self.course_id.id),
            ('state', '=', 'enrolled'),
        ]

    def _compute_student_count(self):
        Enrollment = self.env['umti.student.unit.enrollment'].sudo()
        for rec in self:
            rec.student_count = (
                Enrollment.search_count(rec._get_enrollment_domain())
                if rec.id else 0)

    # ---- Keep student visibility (trainer rules) in sync with timetable ----
    def _refresh_student_trainers(self):
        Enrollment = self.env['umti.student.unit.enrollment'].sudo()
        domains = [[
            ('unit_id', '=', r.unit_id.id),
            ('academic_term_id', '=', r.academic_term_id.id),
            ('state', '=', 'enrolled'),
        ] for r in self if r.unit_id and r.academic_term_id]
        if not domains:
            return
        students = Enrollment.search(expression.OR(domains)).mapped(
            'student_id').sudo()
        if students:
            self.env.add_to_compute(
                students._fields['current_trainer_ids'], students)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_student_trainers()
        return records

    def write(self, vals):
        watched = {'unit_id', 'academic_term_id', 'trainer_id', 'course_id'}
        track = bool(watched & set(vals))
        if track:
            self._refresh_student_trainers()
        res = super().write(vals)
        if track:
            self._refresh_student_trainers()
        return res

    def unlink(self):
        self._refresh_student_trainers()
        return super().unlink()

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id:
            if self.unit_id and self.unit_id not in self.course_id.unit_ids:
                self.unit_id = False
            self.level_id = self.course_id.course_level_id
        else:
            self.unit_id = False
            self.level_id = False

    @api.constrains('facility_id', 'slot_id', 'academic_term_id')
    def _check_room_double_booking(self):
        for rec in self:
            if self.search_count([
                ('id', '!=', rec.id),
                ('facility_id', '=', rec.facility_id.id),
                ('slot_id', '=', rec.slot_id.id),
                ('academic_term_id', '=', rec.academic_term_id.id),
            ]):
                raise ValidationError(_(
                    "Room %(room)s is already booked for this slot in %(term)s.",
                    room=rec.facility_id.display_name,
                    term=rec.academic_term_id.name,
                ))

    @api.constrains('trainer_id', 'slot_id', 'academic_term_id')
    def _check_trainer_double_booking(self):
        for rec in self:
            if self.search_count([
                ('id', '!=', rec.id),
                ('trainer_id', '=', rec.trainer_id.id),
                ('slot_id', '=', rec.slot_id.id),
                ('academic_term_id', '=', rec.academic_term_id.id),
            ]):
                raise ValidationError(_(
                    "Trainer %(trainer)s is already scheduled for this "
                    "slot in %(term)s.",
                    trainer=rec.trainer_id.name,
                    term=rec.academic_term_id.name,
                ))

    @api.constrains('facility_id', 'unit_id', 'academic_term_id')
    def _check_room_capacity(self):
        Enrollment = self.env['umti.student.unit.enrollment']
        for rec in self:
            enrolled = Enrollment.search_count([
                ('unit_id', '=', rec.unit_id.id),
                ('academic_term_id', '=', rec.academic_term_id.id),
                ('state', '=', 'enrolled'),
            ])
            if enrolled > rec.facility_id.capacity:
                raise ValidationError(_(
                    "Room %(room)s (capacity %(cap)d) cannot fit "
                    "%(count)d enrolled students.",
                    room=rec.facility_id.display_name,
                    cap=rec.facility_id.capacity,
                    count=enrolled,
                ))

    # ---- Requirement 4: Facility Unavailability Check ----
    @api.constrains('facility_id', 'slot_id')
    def _check_facility_unavailability(self):
        Unavail = self.env['umti.facility.unavailability']
        for rec in self:
            if Unavail.search_count([
                ('facility_id', '=', rec.facility_id.id),
                ('slot_id', '=', rec.slot_id.id),
            ]):
                raise ValidationError(_(
                    "Facility %(room)s is marked unavailable for "
                    "slot %(slot)s.",
                    room=rec.facility_id.display_name,
                    slot=rec.slot_id.display_name,
                ))


class UmtiExamSchedule(models.Model):
    _name = 'umti.exam.schedule'
    _description = 'Exam Schedule Entry'
    _order = 'exam_date, slot_id'

    # The assessment is the source of truth: everything below that is marked
    # "fetched" is computed from it (and the per-unit dates configured on it),
    # but stays editable so the exam officer can still override a value.
    assessment_id = fields.Many2one(
        'umti.assessment', string='Assessment', required=True)
    exam_date = fields.Date(
        string='Exam Date', required=True,
        compute='_compute_scheduled_values', store=True, readonly=False,
        help="Fetched from the assessment: the unit's own date if one was set "
             "under 'Configure Unit Dates', otherwise the assessment's Exam Date.")
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True,
        compute='_compute_assessment_context', store=True, readonly=False,
        domain="[('status', '=', 'in_progress')]")
    course_id = fields.Many2one(
        'umti.course', string='Course', required=True,
        compute='_compute_assessment_context', store=True, readonly=False)
    department_id = fields.Many2one(
        related='course_id.department_id', store=True, string='Department')
    level_id = fields.Many2one(
        'umti.course.level', string='Level',
        compute='_compute_assessment_context', store=True, readonly=False)
    course_unit_ids = fields.Many2many(
        'umti.course.units', related='course_id.unit_ids',
        string='Course Units')
    unit_id = fields.Many2one(
        'umti.course.units', string='Unit', required=True,
        compute='_compute_assessment_context', store=True, readonly=False,
        domain="[('id', 'in', course_unit_ids)]")
    facility_id = fields.Many2one(
        'umti.facility', string='Exam Hall', required=True,
        compute='_compute_scheduled_values', store=True, readonly=False,
        domain="[('status', '=', 'available')]")
    slot_id = fields.Many2one(
        'umti.timetable.slot', string='Time Slot', required=True,
        compute='_compute_slot', store=True, readonly=False,
        domain="[('slot_type', 'in', ['exam', 'both'])]")
    invigilator_id = fields.Many2one(
        'res.users', string='Invigilator',
        domain="[('share', '=', False)]")
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('published', 'Published'),
    ], string='Status', default='draft', required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    schedule_note = fields.Char(
        string='Schedule Info', compute='_compute_schedule_note')

    # ---- Fetching from the assessment ----
    def _assessment_schedule(self):
        """What the assessment says about when/where this entry takes place.

        Priority: the date configured for the selected unit (Configure Unit
        Dates), then the assessment's own date/time/venue. Nothing is invented:
        if the assessment has no date, ``date`` is False.
        """
        self.ensure_one()
        # sudo: read-only lookup of dates/venue; infrastructure users are not
        # necessarily members of an Exams group.
        a = self.assessment_id.sudo()
        line = a.unit_schedule_ids.filtered(
            lambda l: l.unit_id == self.unit_id and l.date)[:1] \
            if self.unit_id else a.unit_schedule_ids.browse()
        if line:
            return {
                'date': line.date, 'start': line.start_time,
                'end': line.end_time, 'facility': line.facility_id or a.facility_id,
            }
        return {
            'date': a.date, 'start': a.start_time,
            'end': a.end_time, 'facility': a.facility_id,
        }

    @api.depends('assessment_id')
    def _compute_assessment_context(self):
        for rec in self:
            a = rec.assessment_id.sudo()
            if not a:
                # No assessment: keep whatever was entered manually.
                rec.course_id = rec.course_id
                rec.academic_term_id = rec.academic_term_id
                rec.level_id = rec.level_id
                rec.unit_id = rec.unit_id
                continue
            rec.course_id = a.course_id
            rec.academic_term_id = a.semester_id
            rec.level_id = a.level_id or a.course_id.course_level_id
            # Primary unit if the assessment has one, else the first unit that
            # has a date configured. With several undated units the officer picks.
            dated = a.unit_schedule_ids.filtered('date').sorted('date')[:1]
            rec.unit_id = a.unit_id or dated.unit_id

    @api.depends('assessment_id', 'unit_id')
    def _compute_scheduled_values(self):
        for rec in self:
            if not rec.assessment_id:
                rec.exam_date = rec.exam_date
                rec.facility_id = rec.facility_id
                continue
            sched = rec._assessment_schedule()
            # A stale date from another assessment would be worse than none.
            rec.exam_date = sched['date']
            facility = sched['facility']
            # Only pre-fill a hall that can actually be booked; keep a manual pick otherwise.
            rec.facility_id = facility if facility.status == 'available' else rec.facility_id

    @api.depends('exam_date', 'assessment_id', 'unit_id')
    def _compute_slot(self):
        Slot = self.env['umti.timetable.slot']
        for rec in self:
            slot = Slot
            if rec.exam_date:
                slots = Slot.search([
                    ('day_of_week', '=', str(rec.exam_date.weekday())),
                    ('slot_type', 'in', ['exam', 'both']),
                ])
                if rec.assessment_id:
                    start = rec._assessment_schedule()['start']
                    # Exact start first, then the slot the start time falls in.
                    slot = (
                        slots.filtered(lambda s: abs(s.start_time - start) < 1 / 60)
                        or slots.filtered(lambda s: s.start_time <= start < s.end_time)
                    )[:1]
                else:
                    slot = slots[:1]
            if not slot and rec.exam_date and rec.slot_id \
                    and rec.slot_id.day_of_week != str(rec.exam_date.weekday()):
                # A manual pick from another weekday no longer fits the new date.
                rec.slot_id = False
            else:
                rec.slot_id = slot or rec.slot_id

    @api.depends('assessment_id', 'unit_id', 'exam_date', 'slot_id')
    def _compute_schedule_note(self):
        def hhmm(value):
            return '%02d:%02d' % divmod(round(value * 60), 60)

        for rec in self:
            a = rec.assessment_id.sudo()
            if not a:
                rec.schedule_note = False
                continue
            sched = rec._assessment_schedule()
            if not sched['date']:
                rec.schedule_note = _(
                    "Assessment %(name)s has no exam date yet. Set the Exam Date on "
                    "the assessment (or use Configure Unit Dates); it will then be "
                    "fetched here.", name=a.display_name)
                continue
            note = _(
                "Fetched from assessment %(name)s: %(date)s, %(start)s-%(end)s.",
                name=a.display_name,
                date=format_date(self.env, sched['date']),
                start=hhmm(sched['start']), end=hhmm(sched['end']))
            if not rec.slot_id:
                note += ' ' + _(
                    "No exam slot starts at that time on that day - please pick one.")
            rec.schedule_note = note

    @api.constrains('facility_id', 'exam_date', 'slot_id')
    def _check_hall_double_booking(self):
        for rec in self:
            if self.search_count([
                ('id', '!=', rec.id),
                ('facility_id', '=', rec.facility_id.id),
                ('exam_date', '=', rec.exam_date),
                ('slot_id', '=', rec.slot_id.id),
            ]):
                raise ValidationError(_(
                    "Exam hall %(room)s is already booked on %(date)s "
                    "for this slot.",
                    room=rec.facility_id.display_name,
                    date=rec.exam_date,
                ))

    @api.constrains('invigilator_id', 'exam_date', 'slot_id')
    def _check_invigilator_double_booking(self):
        for rec in self.filtered('invigilator_id'):
            if self.search_count([
                ('id', '!=', rec.id),
                ('invigilator_id', '=', rec.invigilator_id.id),
                ('exam_date', '=', rec.exam_date),
                ('slot_id', '=', rec.slot_id.id),
            ]):
                raise ValidationError(_(
                    "Invigilator %(name)s is already assigned on "
                    "%(date)s for this slot.",
                    name=rec.invigilator_id.name,
                    date=rec.exam_date,
                ))

    # ---- Requirement 4: Facility Unavailability Check ----
    @api.constrains('facility_id', 'slot_id')
    def _check_facility_unavailability(self):
        Unavail = self.env['umti.facility.unavailability']
        for rec in self:
            if Unavail.search_count([
                ('facility_id', '=', rec.facility_id.id),
                ('slot_id', '=', rec.slot_id.id),
            ]):
                raise ValidationError(_(
                    "Exam hall %(room)s is marked unavailable for "
                    "slot %(slot)s.",
                    room=rec.facility_id.display_name,
                    slot=rec.slot_id.display_name,
                ))

    def action_confirm(self):
        self.filtered(
            lambda r: r.status == 'draft').write({'status': 'confirmed'})

    def action_publish(self):
        self.filtered(
            lambda r: r.status == 'confirmed').write({'status': 'published'})

    def action_reset_draft(self):
        self.filtered(
            lambda r: r.status != 'draft').write({'status': 'draft'})
