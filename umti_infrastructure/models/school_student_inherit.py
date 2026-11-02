from odoo import api, fields, models
from odoo.osv import expression


class SchoolStudentTimetable(models.Model):
    _inherit = 'school.student'

    class_schedule_ids = fields.Many2many(
        'umti.class.schedule', compute='_compute_class_schedule_ids',
        string='Class Timetable')
    class_schedule_count = fields.Integer(
        compute='_compute_class_schedule_ids', string='Classes')

    def _get_class_schedule_domain(self):
        """Schedules for the units this student is currently enrolled in."""
        self.ensure_one()
        sid = self._origin.id
        if not sid:
            return expression.FALSE_DOMAIN
        enrollments = self.env['umti.student.unit.enrollment'].sudo().search([
            ('student_id', '=', sid), ('state', '=', 'enrolled')])
        combos = {(e.unit_id.id, e.academic_term_id.id, e.course_id.id)
                  for e in enrollments}
        if not combos:
            return expression.FALSE_DOMAIN
        return expression.OR([[
            ('unit_id', '=', u), ('academic_term_id', '=', t),
            ('course_id', '=', c),
        ] for u, t, c in combos])

    @api.depends('enrollment_ids.state', 'enrollment_ids.unit_id',
                 'enrollment_ids.academic_term_id',
                 'enrollment_ids.course_id')
    def _compute_class_schedule_ids(self):
        Schedule = self.env['umti.class.schedule'].sudo()
        for student in self:
            schedules = Schedule.search(student._get_class_schedule_domain())
            student.class_schedule_ids = schedules
            student.class_schedule_count = len(schedules)

    # Class schedules also decide which trainers may see a student.
    @api.depends('enrollment_ids.state', 'enrollment_ids.unit_id',
                 'enrollment_ids.academic_term_id',
                 'enrollment_ids.course_id', 'enrollment_ids.trainer_id')
    def _compute_current_trainers(self):
        super()._compute_current_trainers()
        Schedule = self.env['umti.class.schedule'].sudo()
        for student in self:
            trainers = Schedule.search(
                student._get_class_schedule_domain()).mapped('trainer_id')
            if trainers:
                student.current_trainer_ids = (
                    student.current_trainer_ids | trainers)

    def action_view_timetable(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Class Timetable',
            'res_model': 'umti.class.schedule',
            'view_mode': 'list,form',
            'domain': self._get_class_schedule_domain(),
            'context': {'group_by': ['day_of_week'], 'create': False},
        }
