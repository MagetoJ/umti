from collections import defaultdict

from odoo import http
from odoo.http import request

# A mark is "entered" once the invigilator recorded a score or flagged the
# trainee absent; only entered marks can be verified (see action_verify).
ENTERED = ['|', ('marked', '=', True), ('absent', '=', True)]

# Single source of truth for what each tile counts *and* what it opens, so the
# number on a tile always matches the list behind it.
#
# The exams workflow is:
#   assessment: draft -> scheduled -> open (Marking) -> closed (Completed)
#   mark:       draft -> verified -> published
# "Submitted"/"pending review" therefore means: a Completed assessment whose
# entered marks are still waiting for the exam officer to verify them.
DOMAINS = {
    'assessments_all': [],
    'assessments_draft': [('state', '=', 'draft')],
    'assessments_pending_review': [
        ('state', '=', 'closed'),
        ('mark_ids', 'any', [('state', '=', 'draft')] + ENTERED),
    ],
    'assessments_published': [
        ('state', '=', 'closed'),
        ('mark_ids', '!=', False),
        ('mark_ids', 'not any', [('state', '!=', 'published')]),
    ],
    'marks_all': [],
    'marks_pending': [
        ('state', '=', 'draft'),
        ('assessment_id.state', '=', 'closed'),
    ] + ENTERED,
    'results_all': [],
    'results_pass': [('result', '=', 'pass')],
    'results_fail': [('result', '=', 'fail')],
}


class ExamOfficerDashboardController(http.Controller):

    @http.route('/umti/dashboard/exam_officer_data', type='json', auth='user')
    def exam_officer_data(self, **_kwargs):
        """Aggregates for the Exam Officer dashboard (no new models).

        Runs as the calling user, so ACLs and multi-company record rules apply.
        """
        env = request.env
        Assessment = env['umti.assessment']
        Mark = env['umti.assessment.mark']
        Result = env['umti.unit.result']

        counts = {
            key: model.search_count(domain)
            for key, model, domain in (
                ('assessments_all', Assessment, DOMAINS['assessments_all']),
                ('assessments_draft', Assessment, DOMAINS['assessments_draft']),
                ('assessments_pending_review', Assessment, DOMAINS['assessments_pending_review']),
                ('assessments_published', Assessment, DOMAINS['assessments_published']),
                ('marks_all', Mark, DOMAINS['marks_all']),
                ('marks_pending', Mark, DOMAINS['marks_pending']),
                ('results_all', Result, DOMAINS['results_all']),
                ('results_pass', Result, DOMAINS['results_pass']),
                ('results_fail', Result, DOMAINS['results_fail']),
            )
        }

        return {
            'assessments': {
                'total': counts['assessments_all'],
                'draft': counts['assessments_draft'],
                'pending_review': counts['assessments_pending_review'],
                'published': counts['assessments_published'],
            },
            'marks': {
                'total': counts['marks_all'],
                'pending': counts['marks_pending'],
            },
            'results': {
                'total': counts['results_all'],
                'pass': counts['results_pass'],
                'fail': counts['results_fail'],
            },
            'departments': self._department_stats(),
            'domains': DOMAINS,
        }

    @staticmethod
    def _department_stats():
        """One row per department. Assessments and marks link to a department
        through their course, so group by course in two queries and fold the
        courses into departments in Python (no per-department queries)."""
        env = request.env
        departments = env['umti.department'].search([])

        def dept_of(course):
            return course.sudo().department_id.id

        assessments = defaultdict(int)
        for course, count in env['umti.assessment']._read_group(
                [], ['course_id'], ['__count']):
            assessments[dept_of(course)] += count

        entered = defaultdict(int)
        approved = defaultdict(int)
        for course, state, count in env['umti.assessment.mark']._read_group(
                ENTERED, ['course_id', 'state'], ['__count']):
            dept_id = dept_of(course)
            entered[dept_id] += count
            if state in ('verified', 'published'):
                approved[dept_id] += count

        rows = []
        for dept in departments:
            submitted = entered[dept.id]
            rows.append({
                'id': dept.id,
                'name': dept.name,
                'total_assessments': assessments[dept.id],
                'marks_submitted': submitted,
                'marks_approved': approved[dept.id],
                'marks_pending': submitted - approved[dept.id],
                'progress': round(100.0 * approved[dept.id] / submitted) if submitted else 0,
                'domain': [('course_id.department_id', '=', dept.id)],
            })
        return rows
