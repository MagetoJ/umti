from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTermPatterns(TransactionCase):
    """Patterns resolve course -> level -> default, and generate per course."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.block = env.ref('umti_core.term_pattern_block')
        cls.two_sem = env.ref('umti_core.term_pattern_two_sem')
        cls.department = env['umti.department'].create(
            {'name': 'ICT', 'code': 'ICT'})
        cls.level = env['umti.course.level'].create({
            'name': 'Certificate',
            'term_pattern_id': cls.block.id,
        })
        cls.short_course = env['umti.course'].create({
            'name': 'Hairdressing',
            'code': 'HAIR',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 10,
            'period_type': 'months',
            'period': 6,
        })
        cls.semester_course = env['umti.course'].create({
            'name': 'Diploma in IT',
            'code': 'DIT',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 60,
            'period_type': 'years',
            'period': 2,
        })
        cls.year = env['umti.academic.year'].create({
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 12, 31),
        })

    def test_level_default_and_course_override(self):
        self.assertEqual(
            self.short_course.effective_term_pattern_id, self.block)
        self.short_course.term_pattern_id = self.two_sem
        self.assertEqual(
            self.short_course.effective_term_pattern_id, self.two_sem)
        self.short_course.term_pattern_id = False
        self.assertEqual(
            self.short_course.effective_term_pattern_id, self.block)

    def test_whole_course_block_generation(self):
        terms = self.env['umti.academic.year'].generate_course_terms(
            self.short_course, date(2026, 2, 1), year=self.year)
        self.assertEqual(len(terms), 1)
        term = terms
        self.assertEqual(term.name, 'Hairdressing - Block (Feb 2026)')
        self.assertEqual(term.course_id, self.short_course)
        self.assertEqual(term.academic_year_id, self.year)
        self.assertEqual(term.term_start_date, date(2026, 2, 1))
        self.assertEqual(term.term_end_date, date(2026, 7, 31))
        # Idempotent for the same start date.
        again = self.env['umti.academic.year'].generate_course_terms(
            self.short_course, date(2026, 2, 1), year=self.year)
        self.assertEqual(again, terms)

    def test_year_generation_is_course_scoped_and_idempotent(self):
        self.year.activate_academic_year()
        # The block course is intake-anchored, so the year does not own it.
        self.assertFalse(self.env['umti.academic.term'].search([
            ('academic_year_id', '=', self.year.id),
            ('course_id', '=', self.short_course.id),
        ]))
        # The two-semester course gets its own terms.
        self.semester_course.term_pattern_id = self.two_sem
        self.year._generate_terms()
        terms = self.env['umti.academic.term'].search([
            ('academic_year_id', '=', self.year.id),
            ('course_id', '=', self.semester_course.id),
        ], order='sequence')
        self.assertEqual(len(terms), 2)
        self.assertEqual(terms[0].status, 'in_progress')
        self.assertEqual(terms[1].status, 'draft')
        self.year._generate_terms()
        self.assertEqual(
            self.env['umti.academic.term'].search_count([
                ('academic_year_id', '=', self.year.id),
                ('course_id', '=', self.semester_course.id),
            ]), 2)
