from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

DAY_FIELDS = [
    ('day_mon', '0'), ('day_tue', '1'), ('day_wed', '2'), ('day_thu', '3'),
    ('day_fri', '4'), ('day_sat', '5'), ('day_sun', '6'),
]
DAY_NAMES = [name for name, _code in DAY_FIELDS]

LINE_TYPES = [
    ('regular', 'Class Period'),
    ('exam', 'Exam Session'),
    ('both', 'Class or Exam'),
    ('break', 'Break / Lunch'),
]

#: Line fields whose change must be pushed to the generated slots.
SYNC_FIELDS = {'name', 'line_type', 'start_time', 'end_time', 'template_id'} | set(DAY_NAMES)


class UmtiTimetableSlotTemplate(models.Model):
    """A reusable, named time structure (periods, breaks, exam sessions).

    The lines are the source of truth. ``umti.timetable.slot`` records are
    generated from them (one per line per weekday) and kept in sync when a
    line is edited, so a template can be created once and reused for any
    course, level, term pattern or term.
    """
    _name = 'umti.timetable.slot.template'
    _description = 'Timetable Slot Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    code = fields.Char(string='Code')
    description = fields.Text()
    active = fields.Boolean(default=True)
    auto_apply = fields.Boolean(
        string='Auto-generate Slots', default=True,
        help="Create/update the time slots as soon as a line is saved. "
             "Switch off to review the lines first and press 'Apply'.")
    lock_when_in_use = fields.Boolean(
        string='Protect Running Terms', default=True,
        help="Refuse edits that would move or remove a slot already used by "
             "a class or exam schedule of a running term. Duplicate the "
             "template and assign the copy to the next term instead.")
    line_ids = fields.One2many(
        'umti.slot.template.line', 'template_id', string='Periods', copy=True)
    # Same field as before (kept so existing data is preserved); it is now
    # maintained from the lines.
    slot_ids = fields.Many2many(
        'umti.timetable.slot', string='Time Slots', copy=False)
    line_count = fields.Integer(compute='_compute_counts')
    slot_count = fields.Integer(compute='_compute_counts')
    term_pattern_ids = fields.Many2one(
        'umti.term.pattern', string='Term Pattern',ondelete='cascade',index=True)
    @api.depends('line_ids', 'slot_ids')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.slot_count = len(rec.slot_ids)

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('name', _("%s (copy)", self.name))
        default.setdefault('code', False)
        return super().copy(default)

    def unlink(self):
        self.line_ids._release_slots()
        return super().unlink()

    # ------------------------------------------------------------ Actions
    def action_apply(self):
        """Create/update the slots from the lines (idempotent)."""
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_(
                    "Template '%s' has no periods yet.", rec.name))
        self.line_ids._sync_slots()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Slots are up to date (%d in total).",
                             len(self.slot_ids)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_view_slots(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Slots of %s", self.name),
            'res_model': 'umti.timetable.slot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.slot_ids.ids)],
        }


class UmtiSlotTemplateLine(models.Model):
    _name = 'umti.slot.template.line'
    _description = 'Slot Template Period'
    _order = 'template_id, sequence, start_time, id'

    template_id = fields.Many2one(
        'umti.timetable.slot.template', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Label', required=True)
    line_type = fields.Selection(
        LINE_TYPES, string='Type', default='regular', required=True)
    start_time = fields.Float(required=True, help="24h, e.g. 8.5 = 08:30")
    end_time = fields.Float(required=True, help="24h, e.g. 11.5 = 11:30")
    day_mon = fields.Boolean('Mon', default=True)
    day_tue = fields.Boolean('Tue', default=True)
    day_wed = fields.Boolean('Wed', default=True)
    day_thu = fields.Boolean('Thu', default=True)
    day_fri = fields.Boolean('Fri', default=True)
    day_sat = fields.Boolean('Sat', default=False)
    day_sun = fields.Boolean('Sun', default=False)
    slot_ids = fields.Many2many(
        'umti.timetable.slot', 'umti_slot_line_rel', 'line_id', 'slot_id',
        string='Generated Slots', copy=False, readonly=True)
    duration = fields.Float(compute='_compute_duration')

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            rec.duration = rec.end_time - rec.start_time

    def _day_codes(self):
        self.ensure_one()
        return [code for name, code in DAY_FIELDS if self[name]]

    # --------------------------------------------------------- Constraints
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if not (0 <= rec.start_time < rec.end_time <= 24):
                raise ValidationError(
                    _("Start time must be before end time (0-24)."))

    @api.constrains(*DAY_NAMES)
    def _check_days(self):
        for rec in self:
            if not rec._day_codes():
                raise ValidationError(_(
                    "Period '%s' must run on at least one day.", rec.name))

    @api.constrains('template_id', 'line_type', 'start_time', 'end_time',
                    *DAY_NAMES)
    def _check_overlap_in_template(self):
        for rec in self:
            days = set(rec._day_codes())
            for other in rec.template_id.line_ids - rec:
                if not days & set(other._day_codes()):
                    continue
                if not (rec.start_time < other.end_time
                        and other.start_time < rec.end_time):
                    continue
                # A class period may share time with an exam session, but
                # nothing may overlap a break or a 'both' period.
                if (rec.line_type == other.line_type
                        or 'both' in (rec.line_type, other.line_type)
                        or 'break' in (rec.line_type, other.line_type)):
                    raise ValidationError(_(
                        "Periods '%(a)s' and '%(b)s' overlap in template "
                        "'%(tpl)s'.", a=rec.name, b=other.name,
                        tpl=rec.template_id.name))

    # ------------------------------------------------------ Slot syncing
    def _slot_vals(self, day):
        self.ensure_one()
        return {
            'day_of_week': day,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'slot_type': self.line_type,
            'label': self.name,
        }

    def _get_or_create_slot(self, day):
        """Reuse an identical slot (even an archived one) before creating."""
        self.ensure_one()
        Slot = self.env['umti.timetable.slot'].with_context(active_test=False)
        slot = Slot.search([
            ('day_of_week', '=', day),
            ('start_time', '=', self.start_time),
            ('end_time', '=', self.end_time),
            ('slot_type', '=', self.line_type),
        ], limit=1)
        if slot:
            if not slot.active:
                slot.active = True
            return slot
        vals = self._slot_vals(day)
        vals['template_id'] = self.template_id.id
        # Linked at creation so the slot-level overlap check already knows
        # which template owns the slot.
        vals['line_ids'] = [(4, self.id)]
        return Slot.create(vals)

    def _check_slot_editable(self, slots):
        """Block changes to slots used by a running term (if protected)."""
        self.ensure_one()
        if not self.template_id.lock_when_in_use or not slots:
            return
        Class = self.env['umti.class.schedule'].sudo()
        Exam = self.env['umti.exam.schedule'].sudo()
        domain = [('slot_id', 'in', slots.ids),
                  ('academic_term_id.status', '=', 'in_progress')]
        if Class.search_count(domain) or Exam.search_count(domain):
            raise UserError(_(
                "Period '%(line)s' is used by a class or exam schedule in a "
                "running term, so its slots cannot be moved or removed.\n"
                "Duplicate template '%(tpl)s', change the copy and assign it "
                "to the next term (or switch off 'Protect Running Terms').",
                line=self.name, tpl=self.template_id.name))

    def _sync_slots(self):
        for line in self:
            wanted = [] if line.line_type == 'break' else line._day_codes()
            current = {s.day_of_week: s for s in line.slot_ids}
            removed = self.env['umti.timetable.slot']

            # Days no longer wanted (or the line became a break).
            for day, slot in list(current.items()):
                if day in wanted:
                    continue
                if slot.line_ids == line:
                    line._check_slot_editable(slot)
                line.slot_ids = [(3, slot.id)]
                removed |= slot
                del current[day]

            for day in wanted:
                slot = current.get(day)
                vals = line._slot_vals(day)
                if slot:
                    same = (slot.start_time == line.start_time
                            and slot.end_time == line.end_time
                            and slot.slot_type == line.line_type)
                    exclusive = slot.line_ids == line
                    if same:
                        if exclusive and slot.label != line.name:
                            slot.label = line.name
                        continue
                    if exclusive:
                        line._check_slot_editable(slot)
                        slot.write(vals)      # schedules follow automatically
                        continue
                    line.slot_ids = [(3, slot.id)]  # shared: detach, don't mutate
                target = line._get_or_create_slot(day)
                line.slot_ids = [(4, target.id)]

            line._archive_orphans(removed)
            if line.slot_ids:
                line.template_id.slot_ids = [(4, s) for s in line.slot_ids.ids]
            gone = removed.filtered(lambda s: not s.line_ids)
            if gone:
                line.template_id.slot_ids = [(3, s) for s in gone.ids]

    def _archive_orphans(self, slots):
        """Slots no line points to any more are archived, never deleted, so
        existing schedules keep their history."""
        orphans = slots.filtered(lambda s: not s.line_ids)
        if orphans:
            orphans.write({'active': False})

    def _release_slots(self):
        for line in self:
            exclusive = line.slot_ids.filtered(lambda s: s.line_ids == line)
            line._check_slot_editable(exclusive)
            removed = line.slot_ids
            line.slot_ids = [(5, 0, 0)]
            line._archive_orphans(removed)

    # --------------------------------------------------------------- ORM
    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered(lambda l: l.template_id.auto_apply)._sync_slots()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if SYNC_FIELDS & set(vals):
            self.filtered(
                lambda l: l.slot_ids or l.template_id.auto_apply
            )._sync_slots()
        return res

    def unlink(self):
        self._release_slots()
        return super().unlink()
