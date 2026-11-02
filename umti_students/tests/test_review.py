from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestAdmissionReview(TransactionCase):
    """The live review flow: school.admission.review, not the old popup."""

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
        cls.year = cls.env['umti.academic.year'].create({
            'start_date': '2026-09-01', 'end_date': '2027-06-30'})
        cls.term = cls.env['umti.academic.term'].create({
            'name': 'Semester 1',
            'term_start_date': '2026-09-01',
            'term_end_date': '2027-01-31',
            'academic_year_id': cls.year.id,
            'status': 'in_progress',
        })
        cls.intake = cls.env['school.admission.intake'].create({
            'name': 'DIT Sept 2026',
            'academic_year_id': cls.year.id,
            'semester_id': cls.term.id,
            'course_id': cls.course.id,
            'date_open': '2026-06-01',
            'date_close': '2026-08-31',
        })
        cls.intake.action_open()

    def _application(self, **vals):
        values = {
            'applicant_name': 'Jane Doe',
            'intake_id': self.intake.id,
            'gender': 'female',
            'date_of_birth': '2006-02-01',
            'mobile': '0700000000',
            'guardian_name': 'John Doe',
            'guardian_phone': '0711111111',
        }
        values.update(vals)
        application = self.env['school.admission.application'].create(values)
        application.action_submit()
        return application

    def _review(self, application):
        application.action_start_review()
        return self.env['school.admission.review'].search(
            [('application_id', '=', application.id)], limit=1)

    def test_review_status_opens_the_review_form(self):
        application = self._application()
        action = application.action_view_review_status()
        self.assertEqual(action['res_model'], 'school.admission.review')
        self.assertEqual(action['view_mode'], 'form')
        self.assertFalse(action['res_id'])

    def test_start_review_creates_one_review(self):
        application = self._application()
        review = self._review(application)
        self.assertEqual(application.state, 'review')
        self.assertTrue(review)
        self.assertEqual(review.reviewer_id, self.env.user)
        # Starting again reuses the review instead of creating a second one.
        application.action_start_review()
        self.assertEqual(
            self.env['school.admission.review'].search_count(
                [('application_id', '=', application.id)]), 1)

    def test_accept_is_blocked_while_a_document_is_missing(self):
        document = self.env['umti.course.required.documents'].search([
            ('code', '=', 'kcse'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not document:
            document = self.env['umti.course.required.documents'].create({
                'name': 'KCSE Certificate',
                'code': 'kcse',
                'waivable': False,
            })
        self.course.document_ids = [(4, document.id)]
        application = self._application()
        review = self._review(application)
        review.action_start_review()
        with self.assertRaises(UserError) as caught:
            review.action_accept()
        self.assertIn('KCSE Certificate', str(caught.exception))

    def test_reject_requires_a_reason_and_stores_it(self):
        application = self._application()
        review = self._review(application)
        review.action_start_review()
        with self.assertRaises(UserError):
            review.action_reject()
        review.rejection_reason = 'Incomplete results'
        review.action_reject()
        self.assertEqual(review.state, 'rejected')
        self.assertEqual(application.state, 'rejected')
        self.assertEqual(application.rejection_reason, 'Incomplete results')