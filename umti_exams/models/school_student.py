from odoo import _, api, fields, models


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    assessment_mark_ids = fields.One2many('umti.assessment.mark', 'student_id', string='Assessment Marks')
    unit_result_ids = fields.One2many('umti.unit.result', 'student_id', string='Unit Results')
    published_mark_ids = fields.One2many(
        'umti.assessment.mark', compute='_compute_published_marks', string='Published Marks')

    unit_result_count = fields.Integer(compute='_compute_unit_result_count')

    @api.depends('unit_result_ids')
    def _compute_unit_result_count(self):
        for rec in self:
            rec.unit_result_count = len(rec.unit_result_ids)

    def action_view_unit_results(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Unit Results'),
            'res_model': 'umti.unit.result',
            'view_mode': 'kanban,list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def _compute_published_marks(self):
        for rec in self:
            rec.published_mark_ids = rec.assessment_mark_ids.filtered(
                lambda m: m.state == 'published' and m.assessment_id.state != 'cancelled'
            ).sorted(lambda m: (m.assessment_id.date or fields.Date.today()), reverse=True)
