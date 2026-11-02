from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestAssessment(ExamsCommon):

    def test_code_from_sequence_and_unique(self):
        a = self._assessment()
        self.assertTrue(a.code.startswith('EXM/'))
        self.assertNotEqual(a.code, self._assessment().code)
        with self.assertRaises(Exception), self.cr.savepoint():
            self._assessment(code=a.code)

    def test_time_constraint(self):
        with self.assertRaises(ValidationError):
            self._assessment(start_time=11.0, end_time=9.0)
        with self.assertRaises(ValidationError):
            self._assessment(start_time=9.0, end_time=24.0)
        a = self._assessment(start_time=9.0, end_time=11.5)
        self.assertEqual(a.duration, 2.5)

    def test_schedule_requires_fields(self):
        a = self._assessment(date=False)
        with self.assertRaises(UserError):
            a.action_schedule()
        a.write({'date': '2026-11-20'})
        a.action_schedule()
        self.assertEqual(a.state, 'scheduled')

    def test_open_loads_active_students_from_draft_or_scheduled(self):
        gone = self._student('Gone')
        gone.state = 'suspended'
        a = self._assessment()
        a.action_open()
        self.assertEqual(a.state, 'open')
        self.assertEqual(a.mark_ids.student_id, self.alice | self.bob)

    def test_cancel_and_reset(self):
        a = self._assessment()
        with self.assertRaises(AccessError):
            a.with_user(self.clerk).action_cancel()
        a.with_user(self.manager).action_cancel()
        self.assertEqual(a.state, 'cancelled')
        with self.assertRaises(AccessError):
            a.with_user(self.clerk).action_reset_draft()
        a.with_user(self.manager).action_reset_draft()
        self.assertEqual(a.state, 'draft')
        a.action_open()
        with self.assertRaises(UserError):
            a.action_close()  # unmarked students

    def test_category_computed(self):
        self.assertEqual(self._assessment(assessment_type='final', weight=0).category, 'semester_exam')
        for kind in ('midterm', 'cat', 'quiz', 'assignment', 'practical', 'project'):
            self.assertEqual(self._assessment(assessment_type=kind, weight=0).category, 'periodic')

    def test_one_semester_exam_per_unit_semester(self):
        first = self._assessment(assessment_type='final', weight=50)
        with self.assertRaises(ValidationError) as ctx:
            self._assessment(assessment_type='final', weight=10)
        self.assertIn('Databases', str(ctx.exception))
        # other semester and other unit are fine, periodic is unlimited
        self._assessment(assessment_type='final', semester_id=self.sem2.id, weight=10)
        self._assessment(assessment_type='final', unit_id=self.unit2.id, weight=10)
        self._assessment(assessment_type='quiz', weight=10)
        self._assessment(assessment_type='quiz', weight=10)
        # cancelled ones are ignored, and cannot be reset into a clash
        first.with_user(self.manager).action_cancel()
        second = self._assessment(assessment_type='final', weight=10)
        with self.assertRaises(ValidationError):
            first.with_user(self.manager).action_reset_draft()
        self.assertTrue(second)

    def test_optional_type_must_be_enabled_in_plan(self):
        with self.assertRaises(ValidationError):
            self.env['umti.assessment'].create({
                'name': 'Quiz', 'course_id': self.course.id, 'unit_id': self.unit.id,
                'academic_year_id': self.year.id, 'semester_id': self.sem1.id,
                'assessment_type': 'quiz', 'max_marks': 10})
        self._enable_type('quiz')
        self.assertTrue(self._assessment(assessment_type='quiz'))

    def test_unit_must_belong_to_course_and_semester_to_year(self):
        with self.assertRaises(ValidationError):
            self._assessment(unit_id=self.other_unit.id)
        other_year = self.env['umti.academic.year'].create(
            {'start_date': '2030-10-01', 'end_date': '2031-09-30'})
        with self.assertRaises(ValidationError):
            self._assessment(academic_year_id=other_year.id)

    def test_pass_marks_default_validation_and_warning(self):
        a = self._assessment(max_marks=100)
        self.assertEqual(a.pass_marks, 50)
        a.max_marks = 20
        self.assertEqual(a.pass_marks, 10)
        self.assertFalse(a.pass_marks_warning)
        a.pass_marks = 8
        self.assertTrue(a.pass_marks_warning)
        a.max_marks = 40  # user edit is kept
        self.assertEqual(a.pass_marks, 8)
        with self.assertRaises(ValidationError):
            a.pass_marks = 41
        with self.assertRaises(ValidationError):
            a.pass_marks = -1
