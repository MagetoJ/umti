from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UmtiExamPeriod(models.Model):
    """A reusable exam window: date range + session template + off-days.

    Duplicate it for the next term and only change the semester and dates.
    """
    _name = 'umti.exam.period'
    _description = 'Exam Period'
    _order = 'date_from desc, id'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True,
        ondelete='cascade', index=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    slot_template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Session Template',
        help="Exam sessions available inside this period. Empty: use the "
             "semester's template, then every exam slot.")
    exclusion_ids = fields.One2many(
        'umti.exam.period.exclusion', 'period_id', string='Excluded Dates',
        copy=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    schedule_count = fields.Integer(compute='_compute_counts')
    session_count = fields.Integer(
        string='Available Sessions', compute='_compute_counts')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise ValidationError(_("The period must end after it starts."))

    @api.constrains('exclusion_ids', 'date_from', 'date_to')
    def _check_exclusions(self):
        for rec in self:
            for ex in rec.exclusion_ids:
                if not (rec.date_from <= ex.date <= rec.date_to):
                    raise ValidationError(_(
                        "Excluded date %s is outside the period.", ex.date))

    @api.depends('date_from', 'date_to', 'slot_template_id',
                 'exclusion_ids.date', 'academic_term_id')
    def _compute_counts(self):
        Schedule = self.env['umti.exam.schedule']
        for rec in self:
            rec.schedule_count = Schedule.search_count(
                [('exam_period_id', '=', rec.id)]) if rec.id else 0
            rec.session_count = (
                len(rec._available_sessions())
                if rec.date_from and rec.date_to else 0)

    @api.onchange('academic_term_id')
    def _onchange_academic_term_id(self):
        term = self.academic_term_id
        if not term:
            return
        if not self.name:
            self.name = _("%s - Exams", term.name)
        if not self.slot_template_id:
            self.slot_template_id = term._resolve_slot_template()
        if not self.date_to:
            self.date_to = term.term_end_date
        if not self.date_from and self.date_to:
            self.date_from = self.date_to - timedelta(days=13)

    def _exam_slots(self):
        self.ensure_one()
        Slot = self.env['umti.timetable.slot']
        kinds = ('exam', 'both')
        slots = self.slot_template_id.slot_ids
        if not slots:
            slots = self.academic_term_id._get_allowed_slots()
        slots = slots.filtered(lambda s: s.slot_type in kinds)
        return slots or Slot.search([('slot_type', 'in', kinds)])

    def _available_sessions(self):
        """All (date, slot) pairs the period offers, off-days removed."""
        self.ensure_one()
        by_day = defaultdict(list)
        for slot in self._exam_slots().sorted('start_time'):
            by_day[slot.day_of_week].append(slot)
        excluded = set(self.exclusion_ids.mapped('date'))
        out, day = [], self.date_from
        while day <= self.date_to:
            if day not in excluded:
                out += [(day, s) for s in by_day.get(str(day.weekday()), [])]
            day += timedelta(days=1)
        return out

    def _free_sessions(self, facility=None):
        """Sessions with no exam booked (in that hall, or in any hall)."""
        self.ensure_one()
        domain = [('exam_date', '>=', self.date_from),
                  ('exam_date', '<=', self.date_to)]
        if facility:
            domain.append(('facility_id', '=', facility.id))
        taken = {(e.exam_date, e.slot_id.id)
                 for e in self.env['umti.exam.schedule'].search(domain)}
        return [(d, s) for d, s in self._available_sessions()
                if (d, s.id) not in taken]

    def action_view_schedules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Exams in %s", self.name),
            'res_model': 'umti.exam.schedule',
            'view_mode': 'list,form',
            'domain': [('exam_period_id', '=', self.id)],
            'context': {'default_exam_period_id': self.id,
                        'default_academic_term_id': self.academic_term_id.id},
        }


class UmtiExamPeriodExclusion(models.Model):
    _name = 'umti.exam.period.exclusion'
    _description = 'Exam Period Excluded Date'
    _order = 'date'

    period_id = fields.Many2one(
        'umti.exam.period', required=True, ondelete='cascade', index=True)
    date = fields.Date(required=True)
    reason = fields.Char(help="e.g. Public holiday")

    _sql_constraints = [
        ('period_date_uniq', 'unique(period_id, date)',
         'This date is already excluded.'),
    ]
