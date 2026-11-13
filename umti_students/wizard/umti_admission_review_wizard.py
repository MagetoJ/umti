# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class UmtiAdmissionReviewWizard(models.TransientModel):
    """Popup used by admissions staff to review one online application.

    It only shows data and calls the application's own pipeline methods
    (action_start_review / action_accept / action_reject / action_create_student),
    so every existing check (mandatory documents, intake capacity, admission fee)
    still applies. Nothing is bypassed.
    """
    _name = 'umti.admission.review.wizard'
    _description = 'Umti Admission Review Popup'

    application_id = fields.Many2one(
        'school.admission.application', string='Application',
        required=True, readonly=True)

    # --- read-only snapshot of what the applicant submitted ---------------
    application_no = fields.Char(related='application_id.name', readonly=True)
    state = fields.Selection(related='application_id.state', readonly=True)
    intake_id = fields.Many2one(related='application_id.intake_id', readonly=True)
    course_id = fields.Many2one(related='application_id.course_id', readonly=True)
    academic_year_id = fields.Many2one(related='application_id.academic_year_id', readonly=True)
    semester_id = fields.Many2one(related='application_id.intake_id.semester_id', readonly=True)

    applicant_name = fields.Char(related='application_id.applicant_name', readonly=True)
    gender = fields.Selection(related='application_id.gender', readonly=True)
    date_of_birth = fields.Date(related='application_id.date_of_birth', readonly=True)
    nationality_id = fields.Many2one(related='application_id.nationality_id', readonly=True)
    mobile = fields.Char(related='application_id.mobile', readonly=True)
    email = fields.Char(related='application_id.email', readonly=True)

    guardian_name = fields.Char(related='application_id.guardian_name', readonly=True)
    guardian_relationship = fields.Selection(
        related='application_id.guardian_relationship', readonly=True)
    guardian_phone = fields.Char(related='application_id.guardian_phone', readonly=True)

    currency_id = fields.Many2one(related='application_id.currency_id', readonly=True)
    admission_fee = fields.Monetary(
        related='application_id.admission_fee', currency_field='currency_id', readonly=True)
    fee_paid = fields.Boolean(related='application_id.fee_paid', readonly=True)
    fee_reference = fields.Char(related='application_id.fee_reference', readonly=True)

    missing_documents = fields.Char(
        related='application_id.missing_documents', readonly=True)
    document_ids = fields.One2many(
        related='application_id.document_ids', string='Documents',
        readonly=True)

    # --- what the reviewer enters ----------------------------------------
    reviewer_notes = fields.Text(string='Reviewer Notes')
    rejection_reason = fields.Text(string='Reason for Rejection')

    # ----------------------------------------------------------------------
    def _reopen(self):
        """Refresh the popup so it shows the new status and buttons."""
        return self.application_id.action_open_review_wizard()

    def _log(self, text):
        body = text
        if self.reviewer_notes:
            body = '%s %s' % (text, _('Notes: %s', self.reviewer_notes))
        self.application_id.message_post(body=body)

    def action_start_review(self):
        self.ensure_one()
        if self.application_id.state != 'submitted':
            raise UserError(_('Only submitted applications can be put under review.'))
        self.application_id.action_start_review()
        self._log(_('Review started by %s.', self.env.user.name))
        return self._reopen()

    def action_accept(self):
        self.ensure_one()
        if self.application_id.state != 'review':
            raise UserError(_('Start the review before accepting the application.'))
        self.application_id.action_accept()      # checks documents and intake capacity
        self._log(_('Accepted by %s.', self.env.user.name))
        return self._reopen()

    def action_enrol(self):
        self.ensure_one()
        if self.application_id.state != 'accepted':
            raise UserError(_('Only accepted applications can be enrolled.'))
        self._log(_('Enrolled by %s.', self.env.user.name))
        return self.application_id.action_create_student()   # checks admission fee

    def action_reject(self):
        self.ensure_one()
        if self.application_id.state not in ('submitted', 'review'):
            raise UserError(_('Only submitted or under-review applications can be rejected.'))
        if not self.rejection_reason:
            raise UserError(_('Please enter a reason for rejection.'))
        self.application_id.rejection_reason = self.rejection_reason
        self.application_id.action_reject()
        self._log(_('Rejected by %s. Reason: %s', self.env.user.name, self.rejection_reason))
        return {'type': 'ir.actions.act_window_close'}
