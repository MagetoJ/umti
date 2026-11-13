from odoo import fields, models


class UmtiDepartmentInherit(models.Model):
    _inherit = 'umti.department'

    # Lives here, not in umti_trainers: umti.unit.result is defined by this
    # module, and umti_trainers loads first (umti_exams depends on it). A field
    # declared there pointed at a comodel that did not exist yet, which the
    # registry reports as "unknown comodel_name".
    unit_result_ids = fields.Many2many(
        'umti.unit.result', 'dept_unit_result_computed_rel', 'dept_id',
        'result_id', compute='_compute_unit_result_ids',
        string='Unit Results')

    def _compute_unit_result_ids(self):
        Result = self.env['umti.unit.result']
        for dept in self:
            dept.unit_result_ids = Result.search([
                ('unit_id.department_ids', 'in', dept.id),
            ])
