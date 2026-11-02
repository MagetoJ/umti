from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestUnitResult(ExamsCommon):

    def _result(self, student=None):
        return self.env['umti.unit.result'].search([
            ('student_id', '=', student or self.alice.id), ('unit_id', '=', self.unit.id),
            ('semester_id', '=', self.sem1.id)])

    def _core(self, cat, assignment, final, publish=('cat', 'assignment', 'final')):
        """Create CAT / Assignment / Final; each argument is (alice, bob) marks."""
        made = {}
        for kind, (alice, bob) in (('cat', cat), ('assignment', assignment), ('final', final)):
            a = self._assessment(assessment_type=kind)
            self._mark_all(a, {self.alice: alice, self.bob: bob})
            if kind in publish:
                self._publish(a)
            made[kind] = a
        return made

    def test_final_mark_is_cat_assignment_exam(self):
        self._core(cat=(50, 80), assignment=(80, 40), final=(80, 40))
        res = self._result()
        self.assertTrue(res.is_complete)
        self.assertEqual((res.cat_percent, res.assignment_percent, res.exam_percent), (50, 80, 80))
        # 50*20% + 80*10% + 80*70%
        self.assertAlmostEqual(res.final_mark, 10 + 8 + 56)
        self.assertEqual((res.grade, res.result), ('B', 'pass'))
        bob = self._result(self.bob.id)
        self.assertAlmostEqual(bob.final_mark, 16 + 4 + 28)
        self.assertEqual((bob.grade, bob.result), ('F', 'fail'))

    def test_only_published_marks_count(self):
        made = self._core(cat=(50, 80), assignment=(80, 40), final=(80, 40), publish=('cat',))
        res = self._result()
        self.assertFalse(res.is_complete)
        self.assertEqual(res.pending_count, 2)
        self.assertAlmostEqual(res.final_mark, 10)
        made['assignment'].with_user(self.manager).action_verify_all()  # verified is not enough
        self.assertEqual(self._result().pending_count, 2)
        made['assignment'].with_user(self.manager).action_publish_all()
        made['final'].with_user(self.manager).action_verify_all()
        made['final'].with_user(self.manager).action_publish_all()
        self.assertTrue(self._result().is_complete)

    def test_incomplete_without_all_three_components(self):
        for kind in ('cat', 'final'):
            a = self._assessment(assessment_type=kind)
            self._mark_all(a, {self.alice: 90, self.bob: 90})
            self._publish(a)
        res = self._result()
        self.assertFalse(res.is_complete)   # no assignment exists yet
        self.assertEqual(res.pending_count, 1)
        with self.assertRaises(UserError):
            res.with_user(self.manager).action_publish()

    def test_optional_types_do_not_count(self):
        self._core(cat=(50, 80), assignment=(80, 40), final=(80, 40))
        before = self._result().final_mark
        quiz = self._assessment(assessment_type='quiz')
        self._mark_all(quiz, {self.alice: 100, self.bob: 100})
        self._publish(quiz)
        midterm = self._assessment(assessment_type='midterm')   # left unmarked
        res = self._result()
        self.assertEqual(res.final_mark, before)
        self.assertTrue(res.is_complete)    # an unfinished optional type never blocks
        self.assertEqual(quiz.mark_ids[:1].weighted_score, 0)
        self.assertTrue(midterm)

    def test_several_cats_are_averaged(self):
        self._core(cat=(40, 40), assignment=(0, 0), final=(0, 0))
        cat2 = self._assessment(assessment_type='cat')
        self._mark_all(cat2, {self.alice: 80, self.bob: 80})
        self._publish(cat2)
        res = self._result()
        self.assertEqual(res.cat_percent, 60)
        self.assertAlmostEqual(res.final_mark, 60 * 20 / 100)

    def test_cancelled_ignored_in_consolidation(self):
        self._core(cat=(50, 50), assignment=(50, 50), final=(50, 50))
        extra = self._assessment(assessment_type='cat')
        extra.action_open()                       # an unpublished extra CAT is pending
        res = self._result()
        self.assertEqual(res.pending_count, 1)
        self.assertFalse(res.is_complete)
        extra.with_user(self.manager).action_cancel()
        res = self._result()
        self.assertEqual(res.pending_count, 0)
        self.assertTrue(res.is_complete)

    def test_publish_result_writes_and_updates_exam_record(self):
        made = self._core(cat=(72, 40), assignment=(72, 40), final=(72, 40))
        res = self._result()
        res.with_user(self.manager).action_publish()
        rec = self.env['umti.exam.record'].search([
            ('student_id', '=', self.alice.id), ('unit_id', '=', self.unit.id)])
        self.assertEqual(len(rec), 1)
        self.assertEqual((rec.marks, rec.grade, rec.result), (72, 'B', 'pass'))
        self.assertEqual(res.exam_record_id, rec)
        # reset a published line: the unit result goes back to draft, record is not duplicated
        final = made['final']
        final.mark_ids.filtered(lambda m: m.student_id == self.alice).with_user(
            self.manager).action_reset_draft()
        res = self._result()
        self.assertEqual(res.state, 'draft')
        self.assertFalse(res.is_complete)
        line = final.mark_ids.filtered(lambda m: m.student_id == self.alice)
        line.marks = 90
        line.with_user(self.manager).action_verify()
        line.with_user(self.manager).action_publish()
        res = self._result()
        res.with_user(self.manager).action_publish()
        rec = self.env['umti.exam.record'].search([
            ('student_id', '=', self.alice.id), ('unit_id', '=', self.unit.id)])
        self.assertEqual(len(rec), 1)
        # 72*20% + 72*10% + 90*70%
        self.assertAlmostEqual(rec.marks, 14.4 + 7.2 + 63)

    def test_publish_result_manager_only(self):
        self._core(cat=(72, 40), assignment=(72, 40), final=(72, 40))
        with self.assertRaises(AccessError):
            self._result().with_user(self.clerk).action_publish()
