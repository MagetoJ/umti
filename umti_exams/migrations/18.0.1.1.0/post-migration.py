from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Move to department assessment plans.

    Creates a default plan (CAT / Assignment / Final Exam) for every semester
    and department that already has assessments, then recomputes all unit
    results so only the three core components count. Quizzes, mid-terms,
    practicals and projects stay recorded but no longer affect final marks.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Plan = env['umti.assessment.plan']
    assessments = env['umti.assessment'].search([('state', '!=', 'cancelled')])
    seen = set()
    for a in assessments:
        key = (a.semester_id.id, a.department_id.id)
        if a.semester_id and a.department_id and key not in seen:
            seen.add(key)
            plan = Plan._get_or_create(a.semester_id, a.department_id)
            # Optional types already in use stay enabled so nothing is orphaned.
            used = set(assessments.filtered(
                lambda x: x.semester_id == a.semester_id
                and x.department_id == a.department_id).mapped('assessment_type'))
            plan.line_ids.filtered(
                lambda l: not l.is_core and l.assessment_type in used).write({'enabled': True})

    keys = assessments.mark_ids._result_keys()
    results = env['umti.unit.result'].search([])
    keys |= {(r.student_id.id, r.unit_id.id, r.semester_id.id, r.academic_year_id.id)
             for r in results}
    env['umti.unit.result']._refresh(keys)
