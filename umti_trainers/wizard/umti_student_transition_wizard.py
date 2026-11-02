from odoo import _, api, fields, models
from odoo.exceptions import UserError


class UmtiStudentTransitionWizard(models.TransientModel):
    _name = 'umti.student.transition.wizard'
    _description = 'Student Semester Transition Wizard'

    current_term_id = fields.Many2one(
        'umti.academic.term', string='Current Term', required=True)
    next_term_id = fields.Many2one(
        'umti.academic.term', string='Next Term', required=True)
    course_id = fields.Many2one(
        'umti.course', string='Course', required=True)
    current_level_id = fields.Many2one(
        'umti.course.level', string='Current Level')
    next_level_id = fields.Many2one(
        'umti.course.level', string='Next Level')
    student_ids = fields.Many2many(
        'school.student', 'transition_wizard_student_rel',
        'wizard_id', 'student_id', string='Students')

    @api.onchange('current_term_id', 'course_id')
    def _onchange_load_students(self):
        if not (self.current_term_id and self.course_id):
            return
        enrollments = self.env['umti.student.unit.enrollment'].search([
            ('academic_term_id', '=', self.current_term_id.id),
            ('course_id', '=', self.course_id.id),
            ('state', '=', 'enrolled'),
        ])
        self.student_ids = enrollments.mapped('student_id')

    def action_transit_students(self):
        self.ensure_one()
        if not self.student_ids:
            raise UserError(_("No students selected for transition."))
        if not self.next_term_id:
            raise UserError(_("Please select the next semester."))

        Enrollment = self.env['umti.student.unit.enrollment']

        # 1. Mark previous enrollments as completed
        current_enrollments = Enrollment.search([
            ('student_id', 'in', self.student_ids.ids),
            ('academic_term_id', '=', self.current_term_id.id),
            ('course_id', '=', self.course_id.id),
            ('state', '=', 'enrolled'),
        ])
        current_enrollments.write({'state': 'completed'})

        # 2. Determine target units for the next level
        target_units = self.course_id.unit_ids
        if self.next_level_id:
            level_year_map = {
                'yr_one': 'yr_one',
                'yr_two': 'yr_two',
                'yr_three': 'yr_three',
                'yr_four': 'yr_four',
            }
            target_units = target_units.filtered(
                lambda u: u.unit_level in level_year_map.values())

        # 3. Create new enrolled records for next term
        vals_list = []
        for student in self.student_ids:
            existing = Enrollment.search([
                ('student_id', '=', student.id),
                ('academic_term_id', '=', self.next_term_id.id),
            ]).mapped('unit_id')
            for unit in target_units - existing:
                vals_list.append({
                    'student_id': student.id,
                    'course_id': self.course_id.id,
                    'unit_id': unit.id,
                    'academic_term_id': self.next_term_id.id,
                    'state': 'enrolled',
                })
        if vals_list:
            Enrollment.create(vals_list)

        # 4. Update level on students
        if self.next_level_id:
            self.student_ids.write({'level_id': self.next_level_id.id})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Transition Complete'),
                'message': _('%d students transitioned successfully.') % len(self.student_ids),
                'type': 'success',
                'sticky': False,
            },
        }
