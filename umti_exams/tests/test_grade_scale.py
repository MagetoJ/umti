from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestGradeScale(ExamsCommon):

    def test_seeded_old_bands(self):
        scale = self.env['umti.grade.scale']._get_default()
        self.assertTrue(scale)
        for pct, grade in [(100, 'A'), (80, 'A'), (79.9, 'B'), (70, 'B'), (65, 'C'),
                           (50, 'D'), (49.9, 'F'), (0, 'F')]:
            self.assertEqual(scale.grade_for(pct), grade, pct)
        self.assertTrue(scale.is_pass(50))
        self.assertFalse(scale.is_pass(49))

    def test_one_default_per_company(self):
        with self.assertRaises(ValidationError):
            self.env['umti.grade.scale'].create({
                'name': 'Second', 'is_default': True,
                'line_ids': [(0, 0, {'from_percent': 0, 'grade': 'F'})]})

    def test_scale_needs_lines_and_zero_line(self):
        with self.assertRaises(ValidationError):
            self.env['umti.grade.scale'].create({'name': 'Empty'})
        with self.assertRaises(ValidationError):
            self.env['umti.grade.scale'].create({
                'name': 'No zero', 'line_ids': [(0, 0, {'from_percent': 40, 'grade': 'P'})]})

    def test_exam_record_uses_scale(self):
        record = self.env['umti.exam.record'].create({
            'student_id': self.alice.id, 'academic_year_id': self.year.id,
            'semester_id': self.sem1.id, 'course_id': self.course.id,
            'unit_id': self.unit.id, 'marks': 45, 'max_marks': 100})
        self.assertEqual((record.grade, record.result), ('F', 'fail'))
        record.marks = 55
        self.assertEqual((record.grade, record.result), ('D', 'pass'))
        record.marks = 85
        self.assertEqual(record.grade, 'A')
