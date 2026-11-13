from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Rebuild every unit result with the per-assessment weights."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Mark = env['umti.assessment.mark'].sudo()
    Result = env['umti.unit.result'].sudo()
    keys = Mark.search([])._result_keys()
    keys |= {(r.student_id.id, r.unit_id.id, r.semester_id.id, r.academic_year_id.id)
             for r in Result.search([])}
    Result._refresh(keys)
