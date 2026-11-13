from odoo import api, fields, models


class UmtiAcademicTermInherit(models.Model):
    _inherit = 'umti.academic.term'

    slot_template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Slot Template',
        help="Time structure for this term's class and exam schedules. "
             "Filled automatically from the course, level or term pattern "
             "when the term is started, so later changes to those defaults "
             "do not touch a running term.")
    effective_slot_template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Effective Slot Template',
        compute='_compute_effective_slot_template_id')
    exam_period_ids = fields.One2many('umti.exam.period', 'academic_term_id')

    def _resolve_slot_template(self, course=None):
        """term -> parent term -> course -> level -> term pattern."""
        self.ensure_one()
        Template = self.env['umti.timetable.slot.template']
        found = self.slot_template_id or self.parent_term.slot_template_id
        if found:
            return found
        course = course or self.course_id
        if course:
            return (course.slot_template_id
                    or course.course_level_id.slot_template_id
                    or course.effective_term_pattern_id.slot_template_id
                    or Template)
        return self.pattern_id.slot_template_id or Template

    @api.depends('slot_template_id', 'parent_term.slot_template_id',
                 'course_id.slot_template_id',
                 'course_id.course_level_id.slot_template_id',
                 'pattern_id.slot_template_id')
    def _compute_effective_slot_template_id(self):
        for term in self:
            term.effective_slot_template_id = term._resolve_slot_template()

    def _get_allowed_slots(self, course=None):
        """Slots selectable for this term. Empty recordset when the term has
        no (applied) template; callers then fall back to every slot."""
        Slot = self.env['umti.timetable.slot']
        term = self[:1]
        if not term:
            return Slot
        return term._resolve_slot_template(course=course).slot_ids

    def action_activate_academic_term(self):
        for term in self.filtered(lambda t: not t.slot_template_id):
            term.slot_template_id = term._resolve_slot_template()
        return super().action_activate_academic_term()
