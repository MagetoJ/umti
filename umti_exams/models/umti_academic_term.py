from odoo import _, api, fields, models


class UmtiAcademicTerm(models.Model):
    _inherit = 'umti.academic.term'

    assessment_plan_ids = fields.One2many(
        'umti.assessment.plan', 'semester_id', string='Assessment Plans')
    assessment_plan_count = fields.Integer(compute='_compute_assessment_plan_count')

    @api.depends('assessment_plan_ids')
    def _compute_assessment_plan_count(self):
        for term in self:
            term.assessment_plan_count = len(term.assessment_plan_ids)

    @api.model_create_multi
    def create(self, vals_list):
        terms = super().create(vals_list)
        # Departments' plans exist from day one so HODs can set them up
        # while the semester is still in draft.
        terms._ensure_assessment_plans()
        return terms

    def action_activate_academic_term(self):
        res = super().action_activate_academic_term()
        self._ensure_assessment_plans()
        # Starting the semester locks whatever each department decided
        # (the default CAT / Assignment / Final Exam plan if nothing was changed).
        self.assessment_plan_ids.sudo().filtered(
            lambda p: p.state == 'draft').write({'state': 'confirmed'})
        return res

    def _ensure_assessment_plans(self):
        Plan = self.env['umti.assessment.plan']
        departments = self.env['umti.department'].sudo().search([])
        for term in self:
            for dept in departments:
                if term.company_id and dept.company_id != term.company_id:
                    continue
                Plan._get_or_create(term, dept)

    def action_view_assessment_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Assessment Plans"),
            'res_model': 'umti.assessment.plan',
            'view_mode': 'list,form',
            'domain': [('semester_id', '=', self.id)],
            'context': {'default_semester_id': self.id},
        }
