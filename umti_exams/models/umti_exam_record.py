# -*- coding: utf-8 -*-
from odoo import api, models

from .score_utils import percentage


class UmtiExamRecord(models.Model):
    _inherit = 'umti.exam.record'

    @api.depends('marks', 'max_marks', 'company_id')
    def _compute_result(self):
        Scale = self.env['umti.grade.scale']
        for rec in self:
            pct = percentage(rec.marks, rec.max_marks)
            rec.percentage = pct

            scale = Scale._get_default(rec.company_id)
            if scale:
                rec.grade = scale.grade_for(pct)
                rec.result = 'pass' if scale.is_pass(pct) else 'fail'
            else:
                # Fallback to base computation if no default grading scale is defined
                super(UmtiExamRecord, rec)._compute_result()