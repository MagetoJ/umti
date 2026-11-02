from odoo.tests import HttpCase, tagged

from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestExamOfficerDashboard(ExamsCommon, HttpCase):

    def setUp(self):
        super().setUp()
        self.manager.password = 'exam_manager'
        # One completed assessment with entered (draft) marks: pending review.
        self.closed = self._assessment(name='Closed CAT')
        self._mark_all(self.closed, {self.alice: 80.0, self.bob: 20.0})
        # One assessment still in draft.
        self.draft = self._assessment(name='Draft CAT', code='DRAFT-1')

    def _payload(self):
        self.authenticate('exam_manager', 'exam_manager')
        return self.make_jsonrpc_request('/umti/dashboard/exam_officer_data', {})

    def test_tiles_match_their_click_through_domains(self):
        """The number on a tile must equal the length of the list it opens."""
        data = self._payload()
        env = self.env(user=self.manager)
        domains = data['domains']
        expected = {
            ('assessments', 'total'): ('umti.assessment', 'assessments_all'),
            ('assessments', 'draft'): ('umti.assessment', 'assessments_draft'),
            ('assessments', 'pending_review'): ('umti.assessment', 'assessments_pending_review'),
            ('assessments', 'published'): ('umti.assessment', 'assessments_published'),
            ('marks', 'total'): ('umti.assessment.mark', 'marks_all'),
            ('marks', 'pending'): ('umti.assessment.mark', 'marks_pending'),
            ('results', 'total'): ('umti.unit.result', 'results_all'),
            ('results', 'pass'): ('umti.unit.result', 'results_pass'),
            ('results', 'fail'): ('umti.unit.result', 'results_fail'),
        }
        for (group, key), (model, domain_key) in expected.items():
            self.assertEqual(
                data[group][key], env[model].search_count(domains[domain_key]),
                f"{group}.{key} disagrees with its domain")

    def test_pending_review_and_marks(self):
        data = self._payload()
        self.assertGreaterEqual(data['assessments']['draft'], 1)
        self.assertGreaterEqual(data['assessments']['pending_review'], 1)
        # Alice's and Bob's marks are entered, unverified, on a closed assessment.
        self.assertGreaterEqual(data['marks']['pending'], 2)

    def test_verified_marks_leave_the_pending_queue(self):
        before = self._payload()
        self.closed.mark_ids.with_user(self.manager).action_verify()
        after = self._payload()
        self.assertEqual(after['marks']['pending'], before['marks']['pending'] - 2)

    def test_department_rows(self):
        data = self._payload()
        row = next(d for d in data['departments'] if d['name'] == 'ICT')
        self.assertGreaterEqual(row['total_assessments'], 2)
        self.assertEqual(row['marks_pending'], row['marks_submitted'] - row['marks_approved'])
        self.assertTrue(0 <= row['progress'] <= 100)
