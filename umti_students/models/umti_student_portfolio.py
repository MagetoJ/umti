# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    exam_record_ids = fields.One2many('umti.exam.record', 'student_id', string='Exam Records')
    exam_record_count = fields.Integer(compute='_compute_counts')

    @api.depends('exam_record_ids')
    def _compute_counts(self):
        for rec in self:
            rec.exam_record_count = len(rec.exam_record_ids)

    def action_view_exam_records(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exam Records',
            'res_model': 'umti.exam.record',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
