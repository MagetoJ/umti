import base64

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestAdmission(TransactionCase):
    """Admission documents come from the course, not from fixed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kcse = cls.env.ref('umti_core.kcse_certificate_preset')
        cls.passport = cls.env.ref('umti_core.passport_preset')
        cls.department = cls.env['umti.department'].create(
            {'name': 'ICT', 'code': 'ICT'})
        cls.level = cls.env['umti.course.level'].create({'name': 'Diploma'})
        cls.course = cls.env['umti.course'].create({
            'name': 'Diploma in IT',
            'code': 'DIT',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 30,
            'period_type': 'years',
            'period': 2,
            # The intake capacity is computed from the course.
            'course_capacity': 1,
            'document_ids': [(6, 0, (cls.kcse | cls.passport).ids)],
        })
        cls.year = cls.env['umti.academic.year'].create({
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        })
        cls.year.activate_academic_year()
        cls.term = cls.year.academic_term_ids.filtered(
            lambda term: not term.parent_term)[:1]
        cls.intake = cls.env['school.admission.intake'].create({
            'name': 'DIT Sept 2026',
            'academic_year_id': cls.year.id,
            'semester_id': cls.term.id,
            'course_id': cls.course.id,
            'date_open': '2026-06-01',
            'date_close': '2026-08-31',
        })
        cls.intake.action_open()

    def _application(self, name='Jane Doe'):
        return self.env['school.admission.application'].create({
            'applicant_name': name,
            'intake_id': self.intake.id,
            'gender': 'female',
            'date_of_birth': '2006-02-01',
            'mobile': '0700000000',
            'guardian_name': 'John Doe',
            'guardian_phone': '0711111111',
        })

    def _fee_structure_line(self):
        votehead = self.env.ref('umti_core.admission_structure_votehead')
        structure = self.env['umti.fee.structure'].create({
            'name': 'Fees', 'code': 'FEES'})
        return self.env['umti.fee.structure.line'].create({
            'structure_id': structure.id,
            'course_id': self.course.id,
            'votehead': votehead.id,
            'department_id': self.department.id,
            'academic_year_id': self.year.id,
            'amount': 500,
        })

    def _line(self, application, requirement):
        return application.document_ids.filtered(
            lambda line: line.requirement_id == requirement)

    def test_document_lines_follow_course_requirements(self):
        application = self._application()
        self.assertEqual(application.document_ids.requirement_id,
                         self.kcse | self.passport)
        self.assertEqual(len(application.document_ids), 2)
        self.assertEqual(application.document_ids.mapped('status'),
                         ['missing', 'missing'])
        self.assertIn(self.kcse.name, application.missing_documents)

    def test_new_requirement_needs_no_code_change(self):
        transcript = self.env['umti.course.required.documents'].create({
            'name': 'Transcript',
            'code': 'transcript',
        })
        self.course.document_ids = [(4, transcript.id)]
        application = self._application()
        line = self._line(application, transcript)
        self.assertEqual(len(line), 1)
        self.assertIn('Transcript', application.missing_documents)

    def test_attachment_and_waiver_clear_the_document(self):
        application = self._application()
        self._line(application, self.kcse).write({
            'attachment': base64.b64encode(b'test'),
            'filename': 'kcse.pdf',
        })
        self.assertEqual(self._line(application, self.kcse).status, 'uploaded')
        self.assertEqual(application.missing_documents, self.passport.name)
        self._line(application, self.passport).action_waive()
        self.assertEqual(self._line(application, self.passport).status, 'waived')
        self.assertFalse(application.missing_documents)

    def test_non_waivable_document_refuses_waiver(self):
        application = self._application()
        with self.assertRaises(ValidationError):
            self._line(application, self.kcse).action_waive()

    def test_accept_requires_documents_then_creates_student(self):
        application = self._application()
        application.action_submit()
        with self.assertRaises(UserError):
            application.action_accept()
        self._line(application, self.kcse).write({
            'attachment': base64.b64encode(b'test'),
            'filename': 'kcse.pdf',
        })
        self._line(application, self.passport).action_waive()
        application.action_accept()
        student = application.student_id
        self.assertTrue(student)
        self.assertEqual(student.document_ids.requirement_id, self.kcse)
        document = student.document_ids
        self.assertFalse(document.attachment)
        self.assertEqual(document.source_attachment,
                         base64.b64encode(b'test'))
        self.assertEqual(document.source_filename, 'kcse.pdf')

    def test_course_requirements_are_tracked_like_documents(self):
        requirement = self.env['umti.course.qualifying.requirement'].create({
            'name': 'KCSE mean grade C+',
            'required_mark': 'C+',
        })
        self.course.qualifying_requirement_ids = [(4, requirement.id)]
        application = self._application()
        line = application.requirement_ids.filtered(
            lambda row: row.qualifying_id == requirement)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.required_mark, 'C+')
        self.assertEqual(line.status, 'pending')
        self.assertIn(requirement.name, application.pending_requirements)
        self._line(application, self.kcse).write({
            'attachment': base64.b64encode(b'test'),
            'filename': 'kcse.pdf',
        })
        self._line(application, self.passport).action_waive()
        with self.assertRaises(UserError):
            application.action_accept()
        line.action_mark_met()
        self.assertFalse(application.pending_requirements)
        application.action_accept()
        self.assertTrue(application.student_id)

    def test_likely_to_reject_follows_the_documents(self):
        application = self._application()
        application.action_start_review()
        review = self.env['school.admission.review'].search(
            [('application_id', '=', application.id)], limit=1)
        self.assertTrue(review.likely_to_reject)
        self.assertIn('2 document(s) missing', review.rejection_hint)
        self._line(application, self.kcse).write({
            'attachment': base64.b64encode(b'x'),
            'filename': 'kcse.pdf',
        })
        self._line(application, self.passport).action_waive()
        self.assertFalse(review.likely_to_reject)
        self.assertFalse(review.rejection_hint)

    def test_review_reset_sends_application_back_to_draft(self):
        application = self._application()
        application.action_submit()
        review = application.action_start_review()
        review.write({'rejection_reason': 'Documents missing'})
        review.action_reject()
        self.assertEqual(application.state, 'rejected')

        review.action_reset_draft()
        self.assertEqual(review.state, 'received')
        self.assertEqual(application.state, 'draft')
        self.assertFalse(review.rejection_reason)
        self.assertFalse(application.rejection_reason)

        # Reviewing again must not create a second review.
        self.assertEqual(application.action_start_review(), review)
        self.assertEqual(
            self.env['school.admission.review'].search_count(
                [('application_id', '=', application.id)]), 1)

    def test_requirements_block_acceptance_even_by_direct_write(self):
        met = self.env['umti.course.qualifying.requirement'].create({
            'name': 'KCSE mean grade C+',
            'required_mark': 'C+',
        })
        waiver = self.env['umti.course.qualifying.requirement'].create({
            'name': 'Proof of residence',
            'waivable': True,
        })
        self.course.qualifying_requirement_ids = [
            (4, met.id), (4, waiver.id)]
        application = self._application()
        self._line(application, self.kcse).write({
            'attachment': base64.b64encode(b'x'),
            'filename': 'kcse.pdf',
        })
        self._line(application, self.passport).action_waive()

        pending = application.requirement_ids.filtered(
            lambda line: line.qualifying_id == met)
        with self.assertRaises(UserError):
            application.action_accept()
        # The statusbar / RPC path must be refused too.
        with self.assertRaises(UserError):
            application.write({'state': 'accepted'})

        pending.action_mark_met()
        application.requirement_ids.filtered(
            lambda line: line.qualifying_id == waiver).action_waive()
        self.assertFalse(application.pending_requirements)
        application.write({'state': 'accepted'})
        self.assertEqual(application.state, 'accepted')

    def test_enrolment_is_the_review_final_step(self):
        fee_line = self._fee_structure_line()
        application = self._application()
        application.action_submit()
        review = application.action_start_review()
        review.action_start_review()
        self.assertEqual(review.state, 'under_review')
        self._line(application, self.kcse).write({
            'attachment': base64.b64encode(b'x'),
            'filename': 'kcse.pdf',
            'verified': True,
        })
        self._line(application, self.passport).action_waive()
        review.action_accept()
        self.assertEqual(review.state, 'accepted')

        # The fee is the only blocker for enrolling.
        with self.assertRaises(UserError):
            review.action_enroll()
        fee_line.unlink()
        application.invalidate_recordset()
        self.assertFalse(application.admission_fee)

        review.action_enroll()
        self.assertEqual(review.state, 'enrolled')
        self.assertEqual(application.state, 'enrolled')
        self.assertTrue(application.student_id)

    def test_capacity_blocks_second_acceptance(self):
        first = self._application('First')
        second = self._application('Second')
        for application in (first, second):
            self._line(application, self.kcse).write({
                'attachment': base64.b64encode(b'x'),
                'filename': 'kcse.pdf',
            })
            self._line(application, self.passport).action_waive()
            application.action_submit()
        first.action_accept()
        with self.assertRaises(UserError):
            second.action_accept()
