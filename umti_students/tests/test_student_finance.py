from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStudentFinance(TransactionCase):
    """The dashboard generates one recurring-fee invoice per student."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.department = env['umti.department'].create(
            {'name': 'ICT', 'code': 'ICT'})
        cls.level = env['umti.course.level'].create({'name': 'Diploma'})
        cls.course = env['umti.course'].create({
            'name': 'Diploma in IT',
            'code': 'DIT-FIN',
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
        cls.year.activate_academic_year()
        cls.student = env['school.student'].create({
            'name': 'Finance Student', 'course_id': cls.course.id})
        cls.student.write({'state': 'active'})
        cls.student.action_initialize_program_semesters()

        cls.structure = env['umti.fee.structure'].create({
            'company_id': env.company.id})
        cls.recurring = env['umti.structure.votehead'].create({
            'name': 'Recurring Test', 'code': 'RECUR_TEST'})
        cls.one_time = env['umti.structure.votehead'].create({
            'name': 'One Time Test', 'code': 'ONCE_TEST',
            'paid_once': True})
        cls.refundable = env['umti.structure.votehead'].create({
            'name': 'Refundable Test', 'code': 'REFUND_TEST',
            'refundable': True})
        cls._line(cls.recurring, 1000)
        cls._line(cls.one_time, 500)
        cls._line(cls.refundable, 300)

    @classmethod
    def _line(cls, votehead, amount):
        return cls.env['umti.fee.structure.line'].create({
            'structure_id': cls.structure.id,
            'course_ids': [(6, 0, cls.course.ids)],
            'academic_year_ids': [(6, 0, cls.year.ids)],
            'department_ids': [(6, 0, cls.department.ids)],
            'votehead': votehead.id,
            'amount': amount,
        })

    def _dashboard(self):
        return self.env['umti.student.finance'].create({
            'academic_year_id': self.year.id,
            'course_id': self.course.id,
            'student_state': 'active',
        })

    def test_generation_excludes_once_and_refundable(self):
        dashboard = self._dashboard()
        self.assertEqual(dashboard.student_count, 1)
        dashboard.action_generate_invoices()
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('umti_student_id', '=', self.student.id),
            ('umti_invoice_kind', '=', 'semester'),
        ])
        self.assertEqual(len(invoices), 1)
        invoice = invoices
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(len(invoice.invoice_line_ids), 1)
        self.assertEqual(invoice.invoice_line_ids.price_unit, 1000)
        self.assertEqual(
            invoice.invoice_line_ids.umti_votehead_id, self.recurring)
        self.assertEqual(invoice.umti_course_id, self.course)
        self.assertEqual(invoice.umti_academic_year_id, self.year)

        dashboard.action_generate_invoices()
        self.assertEqual(self.env['account.move'].search_count([
            ('umti_student_id', '=', self.student.id),
            ('umti_invoice_kind', '=', 'semester'),
        ]), 1)

        fresh = self._dashboard()
        self.assertEqual(fresh.student_count, 1)
        self.assertEqual(fresh.semester_invoice_count, 1)
        self.assertEqual(fresh.invoiced_total, 1000)
        self.assertEqual(fresh.outstanding_total, 1000)
        self.assertEqual(fresh.paid_total, 0)
        self.assertEqual(fresh.unpaid_count, 1)

    def test_intake_recurring_invoice_is_not_duplicated(self):
        """The first term's intake invoice becomes the semester invoice."""
        term = self.student.semester_ids.filtered(
            lambda semester: semester.state == 'active'
        ).academic_term_id[:1]
        self.assertTrue(term)
        intake_invoice = self.env['account.move'].create({
            'partner_id': self.student.partner_id.id,
            'move_type': 'out_invoice',
            'ref': 'Intake Fees - Normal',
            'umti_student_id': self.student.id,
            'umti_academic_term_id': term.id,
            'umti_invoice_kind': 'intake',
            'invoice_line_ids': [(0, 0, {
                'name': self.recurring.name,
                'quantity': 1,
                'price_unit': 1000,
                'umti_votehead_id': self.recurring.id,
            })],
        })
        intake_invoice.action_post()

        dashboard = self._dashboard()
        dashboard.action_generate_invoices()

        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('umti_student_id', '=', self.student.id),
            ('state', '!=', 'cancel'),
        ])
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices, intake_invoice)
        self.assertEqual(invoices.umti_invoice_kind, 'semester')
        self.assertIn('already invoiced', dashboard.last_run_summary)
