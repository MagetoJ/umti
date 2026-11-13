from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


class PortfolioCommon:

    @classmethod
    def _setup_data(cls):
        env = cls.env
        cls.department = env['umti.department'].create({
            'name': 'ICT', 'code': 'ICT'})
        cls.level = env['umti.course.level'].create({'name': 'Diploma'})
        cls.course = env['umti.course'].create({
            'name': 'Diploma in IT', 'code': 'DIT',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 60, 'period_type': 'years', 'period': 2,
        })
        cls.year = env['umti.academic.year'].create({
            'start_date': '2026-09-01', 'end_date': '2027-06-30'})
        cls.semester = env['umti.academic.term'].create({
            'name': 'Semester 1',
            'term_start_date': '2026-09-01',
            'term_end_date': '2027-01-31',
            'academic_year_id': cls.year.id,
            'status': 'in_progress',
        })
        cls.sponsor = env['res.partner'].create({'name': 'County Bursary'})
        cls.student = env['school.student'].create({
            'name': 'Jane Doe', 'course_id': cls.course.id})

    def _fee(self, student=None, **vals):
        values = {
            'student_id': (student or self.student).id,
            'academic_year_id': self.year.id,
            'semester_id': self.semester.id,
            'course_id': self.course.id,
            'fee_amount': 1000,
        }
        values.update(vals)
        return self.env['umti.fee.record'].create(values)


@tagged('post_install', '-at_install')
class TestFeeRecord(PortfolioCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_data()

    def test_balance_is_charge_minus_payment(self):
        fee = self._fee(fee_amount=1000, payment_amount=400)
        self.assertEqual(fee.balance, 600)
        self.assertEqual(fee.record_type, 'payment')

    def test_receipt_number_generated_on_payment(self):
        charge = self._fee()
        self.assertFalse(charge.receipt_no)
        charge.payment_amount = 200
        self.assertTrue(charge.receipt_no.startswith('RCT/'))
        number = charge.receipt_no
        charge.payment_amount = 300
        self.assertEqual(charge.receipt_no, number)
        self.assertNotEqual(self._fee(payment_amount=50).receipt_no, number)

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValidationError):
            self._fee(payment_amount=-1)

    def test_semester_must_belong_to_the_year(self):
        other_year = self.env['umti.academic.year'].create({
            'start_date': '2027-09-01', 'end_date': '2028-06-30'})
        other_semester = self.env['umti.academic.term'].create({
            'name': 'Semester 1',
            'term_start_date': '2027-09-01',
            'term_end_date': '2028-01-31',
            'academic_year_id': other_year.id,
        })
        with self.assertRaises(ValidationError):
            self._fee(semester_id=other_semester.id)
