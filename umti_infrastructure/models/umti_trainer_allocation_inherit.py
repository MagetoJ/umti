from odoo import api, fields, models


class UmtiTrainerAllocationTimetable(models.Model):
    _inherit = 'umti.trainer.allocation'

    class_schedule_ids = fields.Many2many(
        'umti.class.schedule', compute='_compute_class_schedule_ids',
        string='Class Timetable')
    class_schedule_count = fields.Integer(
        compute='_compute_class_schedule_ids', string='Classes')

    @api.depends('employee_id', 'employee_id.user_id')
    def _compute_class_schedule_ids(self):
        Schedule = self.env['umti.class.schedule'].sudo()
        for rec in self:
            trainer = rec.employee_id.user_id
            if trainer:
                schedules = Schedule.search([('trainer_id', '=', trainer.id)])
            else:
                schedules = Schedule
            rec.class_schedule_ids = schedules
            rec.class_schedule_count = len(schedules)

    def action_view_timetable(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Class Timetable',
            'res_model': 'umti.class.schedule',
            'view_mode': 'list,form',
            'domain': [('trainer_id', '=', self.employee_id.user_id.id)],
            'context': {'group_by': ['day_of_week']},
        }
