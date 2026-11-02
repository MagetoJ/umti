from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestMarks(ExamsCommon):

    def setUp(self):
        super().setUp()
        self.a = self._assessment(weight=100)
        self.a.action_open()
        self.line = self.a.mark_ids.filtered(lambda m: m.student_id == self.alice)

    def test_grade_result_and_45_is_not_pass(self):
        self.line.marks = 45
        self.assertEqual((self.line.grade, self.line.result), ('F', 'fail'))
        self.line.marks = 50
        self.assertEqual((self.line.grade, self.line.result), ('D', 'pass'))
        self.line.marks = 91
        self.assertEqual(self.line.grade, 'A')
        # one CAT carries the whole CAT component (20% by default)
        self.assertAlmostEqual(self.line.weighted_score, 91 * 20 / 100)

    def test_absent(self):
        self.line.absent = True
        self.assertEqual(self.line.result, 'absent')
        self.assertFalse(self.line.grade)
        self.assertEqual(self.line.weighted_score, 0)

    def test_mark_validation_and_unique(self):
        with self.assertRaises(ValidationError):
            self.line.marks = -1
        with self.assertRaises(ValidationError):
            self.line.marks = 101
        with self.assertRaises(Exception), self.cr.savepoint():
            self.env['umti.assessment.mark'].create(
                {'assessment_id': self.a.id, 'student_id': self.alice.id})

    def test_verify_needs_closed_and_marked(self):
        self.line.marks = 70
        with self.assertRaises(UserError):
            self.line.with_user(self.manager).action_verify()  # still in marking
        self.a.mark_ids.filtered(lambda m: m.student_id == self.bob).write({'absent': True})
        self.a.action_close()
        self.line.with_user(self.manager).action_verify()
        self.assertEqual(self.line.state, 'verified')

    def test_verify_needs_marked_or_absent(self):
        self.line.marks = 70
        self.a.mark_ids.filtered(lambda m: m.student_id == self.bob).write({'marked': True})
        self.a.action_close()
        bob = self.a.mark_ids.filtered(lambda m: m.student_id == self.bob)
        bob.marked = False
        with self.assertRaises(UserError):
            bob.with_user(self.manager).action_verify()

    def test_publish_needs_verified_and_lock(self):
        self._mark_all_open({self.alice: 70})
        with self.assertRaises(UserError):
            self.line.with_user(self.manager).action_publish()
        self.line.with_user(self.manager).action_verify()
        self.line.with_user(self.manager).action_publish()
        self.assertEqual(self.line.state, 'published')
        for vals in ({'marks': 10}, {'absent': True}, {'remarks': 'x'}):
            with self.assertRaises(UserError):
                self.line.write(vals)
        with self.assertRaises(UserError):
            self.line.unlink()
        self.line.with_user(self.manager).action_reset_draft()
        self.line.marks = 12
        self.assertEqual(self.line.marks, 12)

    def test_manager_only(self):
        self._mark_all_open({self.alice: 70})
        for action in ('action_verify',):
            with self.assertRaises(AccessError):
                getattr(self.line.with_user(self.clerk), action)()
        self.line.with_user(self.manager).action_verify()
        with self.assertRaises(AccessError):
            self.line.with_user(self.clerk).action_publish()
        with self.assertRaises(AccessError):
            self.line.with_user(self.clerk).action_reset_draft()
        with self.assertRaises(AccessError):
            self.a.with_user(self.clerk).action_verify_all()

    def test_bulk_buttons(self):
        self._mark_all_open({self.alice: 70, self.bob: 30})
        self.a.with_user(self.manager).action_verify_all()
        self.assertEqual(set(self.a.mark_ids.mapped('state')), {'verified'})
        self.a.with_user(self.manager).action_publish_all()
        self.assertEqual(set(self.a.mark_ids.mapped('state')), {'published'})
        self.a.with_user(self.manager).action_reset_all_draft()
        self.assertEqual(set(self.a.mark_ids.mapped('state')), {'draft'})

    def test_cancelled_assessment_locks_marks(self):
        self.line.marks = 60
        self.a.with_user(self.manager).action_cancel()
        with self.assertRaises(UserError):
            self.line.marks = 70
        with self.assertRaises(UserError):
            self.env['umti.assessment.mark'].create(
                {'assessment_id': self.a.id, 'student_id': self._student('Late').id})

    def _mark_all_open(self, marks):
        for line in self.a.mark_ids:
            line.marks = marks.get(line.student_id, 0.0)
        self.a.action_close()
