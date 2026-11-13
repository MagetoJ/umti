from datetime import date, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTermProgression(TransactionCase):
    """Units follow the course plan and students advance cohort by cohort."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        two_sem = env.ref('umti_core.term_pattern_two_sem')
        cls.department = env['umti.department'].create(
            {'name': 'ICT', 'code': 'ICT'})
        cls.level = env['umti.course.level'].create({
            'name': 'Diploma',
            'term_pattern_id': two_sem.id,
        })
        cls.unit_one = env['umti.course.units'].create({
            'name': 'Databases', 'code': 'DB1', 'credit_contribution': 3,
            'department_id': cls.department.id,
        })
        cls.unit_two = env['umti.course.units'].create({
            'name': 'Networks', 'code': 'NW1', 'credit_contribution': 3,
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
            'unit_ids': [(6, 0, (cls.unit_one | cls.unit_two).ids)],
            'unit_line_ids': [
                (0, 0, {'unit_id': cls.unit_one.id, 'course_year': 1,
                        'period_sequence': 10}),
                (0, 0, {'unit_id': cls.unit_two.id, 'course_year': 1,
                        'period_sequence': 20}),
            ],
        })
        cls.year = env['umti.academic.year'].create({
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 12, 31),
        })
        cls.year.activate_academic_year()
        cls.terms = env['umti.academic.term'].search([
            ('academic_year_id', '=', cls.year.id),
            ('course_id', '=', cls.course.id),
        ], order='sequence')
        cls.student = env['school.student'].create({
            'name': 'Jane Doe', 'course_id': cls.course.id})
        cls.student.action_initialize_program_semesters()

    def test_units_follow_the_course_plan(self):
        first = self.student.semester_ids.sorted('sequence')[:1]
        self.assertEqual(
            self.student._units_for_semester(first), self.unit_one)
        second = self.student.semester_ids.sorted('sequence')[1:2]
        self.assertEqual(
            self.student._units_for_semester(second), self.unit_two)

    def test_new_student_does_not_adopt_another_courses_term(self):
        other_course = self.env['umti.course'].create({
            'name': 'Business Studies',
            'code': 'BUS',
            'department_id': self.department.id,
            'course_level_id': self.level.id,
            'minimum_credits': 10,
            'period_type': 'years',
            'period': 1,
        })
        today = fields.Date.context_today(self.env.user)
        other_term = self.env['umti.academic.term'].create({
            'name': 'Business current term',
            'term_start_date': today,
            'term_end_date': today + timedelta(days=30),
            'academic_year_id': self.year.id,
            'course_id': other_course.id,
            'status': 'in_progress',
        })
        student = self.env['school.student'].create({
            'name': 'New Student', 'course_id': self.course.id})
        self.assertFalse(student.enrollment_ids)
        term = student._get_current_term()
        self.assertNotEqual(term.course_id, other_course)
        self.assertIn(term, self.terms)

    def test_shared_group_roster_spans_cohort_terms(self):
        term_one, term_two = self.terms
        other = self.env['school.student'].create({
            'name': 'John Doe', 'course_id': self.course.id})
        Enrollment = self.env['umti.student.unit.enrollment']
        Enrollment.create([
            {'student_id': self.student.id, 'course_id': self.course.id,
             'unit_id': self.unit_one.id, 'academic_term_id': term_one.id,
             'state': 'enrolled'},
            {'student_id': other.id, 'course_id': self.course.id,
             'unit_id': self.unit_one.id, 'academic_term_id': term_two.id,
             'state': 'enrolled'},
        ])
        group = self.env['umti.class.group'].create({
            'name': 'Shared Databases',
            'unit_id': self.unit_one.id,
            'term_ids': [(6, 0, (term_one | term_two).ids)],
        })
        sheet = self.env['umti.attendance.sheet'].create({
            'name': 'Shared session',
            'date': date(2026, 2, 2),
            'trainer_id': self.env.user.id,
            'department_id': self.department.id,
            'unit_id': self.unit_one.id,
            'group_id': group.id,
        })
        self.assertEqual(len(sheet._get_roster_enrollments()), 2)

    def test_unit_placement_is_owned_by_each_course(self):
        other_course = self.env['umti.course'].create({
            'name': 'Certificate in IT',
            'code': 'CIT',
            'department_id': self.department.id,
            'course_level_id': self.level.id,
            'minimum_credits': 10,
            'period_type': 'years',
            'period': 1,
            'unit_ids': [(6, 0, self.unit_one.ids)],
        })
        other_line = other_course.unit_line_ids
        self.assertEqual(other_line.unit_id, self.unit_one)
        other_line.write({'period_sequence': 20})
        original = self.course.unit_line_ids.filtered(
            lambda line: line.unit_id == self.unit_one)
        self.assertEqual(original.period_sequence, 10)
        # Changing the catalogue default must not move either course.
        self.unit_one.write({'unit_semester': 'sem_2'})
        self.assertEqual(original.period_sequence, 10)
        self.assertEqual(other_line.period_sequence, 20)

    def test_starting_the_next_term_advances_the_student(self):
        term_one, term_two = self.terms
        first = self.student.semester_ids.sorted('sequence')[:1]
        self.assertEqual(first.academic_term_id, term_one)
        term_one.action_end_academic_term()
        term_two.action_activate_academic_term()
        active = self.student.semester_ids.filtered(
            lambda semester: semester.state == 'active')
        latest = active.sorted('sequence')[-1:]
        self.assertEqual(latest.academic_term_id, term_two)
        self.assertEqual(
            self.student.enrollment_ids.filtered(
                lambda enrollment: enrollment.academic_term_id == term_two
            ).unit_id,
            self.unit_two,
        )
