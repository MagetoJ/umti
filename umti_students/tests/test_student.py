from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestStudent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level = cls.env['umti.course.level'].create({'name': 'Diploma'})
        cls.department = cls.env['umti.department'].create({
            'name': 'ICT', 'code': 'ICT'})
        cls.course = cls.env['umti.course'].create({
            'name': 'Diploma in IT', 'code': 'DIT',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 60, 'period_type': 'years', 'period': 2,
        })
        cls.student = cls.env['school.student'].create({'name': 'Jane Doe'})

    def test_admission_number_generated(self):
        self.assertTrue(self.student.admission_no.startswith('ADM/'))
        self.assertEqual(self.student.state, 'incomplete')

    def test_activation_requires_complete_profile(self):
        with self.assertRaises(UserError):
            self.student.action_activate()

    def test_activation_succeeds_when_complete(self):
        self.student.write({
            'gender': 'female',
            'date_of_birth': '2005-01-01',
            'mobile': '0700000000',
            'email': 'jane.doe@example.com',
            'course_id': self.course.id,
            'guardian_ids': [(0, 0, {
                'name': 'John Doe', 'phone': '0711111111',
                'relationship': 'parent'})],
        })
        self.student.action_activate()
        self.assertEqual(self.student.state, 'active')
        self.assertEqual(self.student.department_id, self.course.department_id)
        self.assertTrue(self.student.user_id)

    def test_hold_blocks_graduation(self):
        self.student.write({'state': 'active', 'has_hold': True})
        with self.assertRaises(UserError) as caught:
            self.student.action_graduate()
        self.assertIn('on hold', str(caught.exception))
        self.student.has_hold = False
        self.student.action_graduate()
        self.assertEqual(self.student.state, 'graduated')
