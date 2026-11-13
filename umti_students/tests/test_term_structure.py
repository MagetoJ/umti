from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestIntakeTerms(TransactionCase):
    """Rolling intakes own their terms and the student ladder follows them."""

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
        cls.course = env['umti.course'].create({
            'name': 'Hairdressing',
            'code': 'HAIR',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 10,
            'period_type': 'months',
            'period': 6,
        })
        cls.year = env['umti.academic.year'].create({
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 12, 31),
        })

    def _intake(self, name, start):
        return self.env['school.admission.intake'].create({
            'name': name,
            'academic_year_id': self.year.id,
            'course_id': self.course.id,
            'date_open': start,
            'date_close': start,
            'start_date': start,
        })

    def _student(self, name, intake):
        application = self.env['school.admission.application'].create({
            'intake_id': intake.id,
            'applicant_name': name,
            'guardian_name': 'Guardian',
            'guardian_phone': '0700000000',
        })
        return self.env['school.student'].create({
            'name': name,
            'course_id': self.course.id,
            'application_id': application.id,
        })

    def test_rolling_intakes_get_their_own_block_term(self):
        first = self._intake('January intake', date(2026, 1, 5))
        first.action_open()
        second = self._intake('March intake', date(2026, 3, 2))
        second.action_open()

        first_term = first.semester_id
        second_term = second.semester_id
        self.assertTrue(first_term)
        self.assertTrue(second_term)
        self.assertNotEqual(first_term, second_term)
        self.assertEqual(first_term.intake_id, first)
        self.assertEqual(second_term.intake_id, second)
        self.assertEqual(first_term.term_start_date, date(2026, 1, 5))
        self.assertEqual(second_term.term_start_date, date(2026, 3, 2))

        jane = self._student('Jane', first)
        jane.action_initialize_program_semesters()
        self.assertEqual(jane.semester_ids.academic_term_id, first_term)
        self.assertEqual(len(jane.semester_ids), 1)
        self.assertEqual(jane.semester_ids.state, 'active')
        self.assertEqual(jane.semester_ids.name,
                         'Hairdressing - Block (Jan 2026)')

        john = self._student('John', second)
        john.action_initialize_program_semesters()
        self.assertEqual(john.semester_ids.academic_term_id, second_term)

    def test_changing_intake_dates_moves_the_existing_term(self):
        intake = self._intake('January intake', date(2026, 1, 5))
        intake.action_open()
        term = intake.semester_id
        intake.write({'start_date': date(2026, 1, 12)})
        self.assertEqual(intake.semester_id, term)
        self.assertEqual(term.term_start_date, date(2026, 1, 12))
        self.assertEqual(term.term_end_date, date(2026, 7, 11))
        self.assertIn('Jan 2026', term.name)
        self.assertEqual(
            self.env['umti.academic.term'].search_count([
                ('intake_id', '=', intake.id)]), 1)
        intake.write({'end_date': date(2026, 6, 30)})
        self.assertEqual(term.term_end_date, date(2026, 6, 30))

    def test_academic_year_course_builds_the_expected_ladder(self):
        academic_level = self.env['umti.course.level'].create({
            'name': 'Diploma',
            'term_pattern_id': self.two_sem.id,
        })
        course = self.env['umti.course'].create({
            'name': 'Diploma in IT',
            'code': 'DIT',
            'department_id': self.department.id,
            'course_level_id': academic_level.id,
            'minimum_credits': 60,
            'period_type': 'years',
            'period': 2,
        })
        self.year.activate_academic_year()
        terms = self.env['umti.academic.term'].search([
            ('academic_year_id', '=', self.year.id),
            ('course_id', '=', course.id),
        ], order='sequence')
        self.assertEqual(len(terms), 2)
        student = self.env['school.student'].create({
            'name': 'Academic Student',
            'course_id': course.id,
        })
        student.action_initialize_program_semesters()
        self.assertEqual(len(student.semester_ids), 4)
        first = student.semester_ids.sorted('sequence')[:1]
        self.assertEqual(first.state, 'active')
        self.assertEqual(first.academic_term_id, terms[0])
