from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGeneratedTermsBanner(TransactionCase):
    """Courses with several generated terms can point users at them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.two_sem = env.ref('umti_core.term_pattern_two_sem')
        cls.block = env.ref('umti_core.term_pattern_block')
        cls.department = env['umti.department'].create(
            {'name': 'ICT', 'code': 'ICT'})
        cls.level = env['umti.course.level'].create({
            'name': 'Diploma', 'term_pattern_id': cls.two_sem.id})
        cls.unit = env['umti.course.units'].create({
            'name': 'Databases', 'code': 'DB1', 'credit_contribution': 3,
            'department_id': cls.department.id,
        })
        cls.course = env['umti.course'].create({
            'name': 'Diploma in IT',
            'code': 'DIT',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 60,
            'period_type': 'years',
            'period': 2,
            'unit_ids': [(6, 0, cls.unit.ids)],
        })
        cls.year = env['umti.academic.year'].create({
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 12, 31),
        })
        cls.year.activate_academic_year()

    def test_banner_lists_terms_and_dismisses(self):
        self.assertTrue(self.course.show_generated_terms_warning)
        self.assertEqual(len(self.course.generated_term_ids), 2)
        self.assertIn('DIT', self.course.generated_term_ids[0].name)
        action = self.course.action_review_generated_terms()
        self.assertTrue(self.course.term_review_dismissed)
        self.assertFalse(self.course.show_generated_terms_warning)
        self.assertEqual(action['res_model'], 'umti.academic.term')

    def test_block_pattern_has_no_banner(self):
        block_level = self.env['umti.course.level'].create({
            'name': 'Certificate', 'term_pattern_id': self.block.id})
        course = self.env['umti.course'].create({
            'name': 'Hairdressing',
            'code': 'HAIR',
            'department_id': self.department.id,
            'course_level_id': block_level.id,
            'minimum_credits': 10,
            'period_type': 'months',
            'period': 6,
            'unit_ids': [(6, 0, self.unit.ids)],
        })
        self.env['umti.academic.year'].generate_course_terms(
            course, date(2026, 2, 1), year=self.year)
        self.assertFalse(course.show_generated_terms_warning)

    def test_course_without_units_has_no_banner(self):
        course = self.env['umti.course'].create({
            'name': 'Network Basics',
            'code': 'NET',
            'department_id': self.department.id,
            'course_level_id': self.level.id,
            'minimum_credits': 10,
            'period_type': 'years',
            'period': 1,
        })
        self.env['umti.academic.year'].generate_course_terms(
            course, self.year.start_date, self.year.end_date, year=self.year)
        self.assertFalse(course.show_generated_terms_warning)
