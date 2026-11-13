from odoo import api, fields, models, _


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    service_case_ids = fields.One2many(
        'umti.student.service.case', 'student_id', string='Service Cases')
    open_service_case_count = fields.Integer(
        compute='_compute_service_case_count')

    @api.depends('service_case_ids.state')
    def _compute_service_case_count(self):
        Case = self.env['umti.student.service.case']
        can_read = self.env.user.has_group(
            'umti_students.group_umti_student_services_user')
        for student in self:
            student.open_service_case_count = (
                Case.search_count([
                    ('student_id', '=', student.id),
                    ('state', 'in', ('new', 'in_progress', 'on_hold')),
                ]) if can_read else 0)

    def action_view_service_cases(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student Services'),
            'res_model': 'umti.student.service.case',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
                'search_default_filter_open': 1,
                'search_default_group_service': 1,
            },
        }

    def action_new_service_case(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Service Case'),
            'res_model': 'umti.student.service.case',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {
                'default_student_id': self.id,
                'default_assigned_to': self.env.user.id,
            },
            'target': 'current',
        }
