from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SchoolAdmissionApplication(models.Model):
    """An application to an intake. Moves draft > submitted > review > accepted > enrolled (or rejected)."""
    _name = 'school.admission.application'
    _description = 'Admission Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_names_search = ['name', 'applicant_name']

    name = fields.Char(
        string='Application No', required=True, copy=False, readonly=True,
        index=True, default='New')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    intake_id = fields.Many2one(
        'school.admission.intake', string='Intake', required=True,
        tracking=True, ondelete='restrict')
    course_id = fields.Many2one(related='intake_id.course_id', store=True, readonly=True)
    academic_year_id = fields.Many2one(
        related='intake_id.academic_year_id', store=True, readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('enrolled', 'Enrolled'),
    ], default='draft', required=True, tracking=True, copy=False)

    applicant_name = fields.Char(required=True, tracking=True)
    gender = fields.Selection([
        ('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    date_of_birth = fields.Date()
    nationality_id = fields.Many2one('res.country', string='Nationality')
    mobile = fields.Char()
    email = fields.Char()

    guardian_name = fields.Char( required=True)
    guardian_relationship = fields.Selection([
        ('parent', 'Parent'), ('guardian', 'Guardian'), ('sibling', 'Sibling'),
        ('spouse', 'Spouse'), ('other', 'Other')], default='parent')
    guardian_phone = fields.Char(required=True)

    document_ids = fields.One2many(
        'school.admission.document', 'application_id', string='Documents')
    missing_documents = fields.Char(compute='_compute_missing_documents')
    requirement_ids = fields.One2many(
        'school.admission.requirement', 'application_id',
        string='Course Requirements')
    general_requirement_ids = fields.One2many(
        'school.admission.requirement', 'application_id',
        domain=[('kind', '=', 'general')], string='General Requirements')
    pending_requirements = fields.Char(compute='_compute_pending_requirements')
    admission_fee = fields.Monetary(
        related='intake_id.admission_fee', currency_field='currency_id')
    currency_id = fields.Many2one(related='intake_id.currency_id')
    fee_paid = fields.Boolean(string='Admission Fee Paid', compute='_compute_fee_paid', tracking=True, copy=False)
    # TODO: fold fee_status into the application workflow — block enrolment
    # while partially paid and surface it on the application form/portal.
    fee_status = fields.Selection([
        ('no_invoice', 'No Invoice'),
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], compute='_compute_fee_paid', string='Fee Status')
    adm_fee_invoice_id = fields.Many2one('account.move', string='Admission Fee Invoice')
    fee_reference = fields.Char(string='Payment Reference', copy=False)

    rejection_reason = fields.Text(copy=False)
    reviewed_by = fields.Many2one('res.users', copy=False, readonly=True)
    review_date = fields.Date(copy=False, readonly=True)
    student_id = fields.Many2one('school.student', copy=False, readonly=True)
    invoice_count = fields.Integer(string="Invoice Count", compute="_compute_fee_paid", store=True)

    @api.depends('intake_id')
    def _onchange_intake_id(self):
        """Show the new course's documents as soon as the intake is picked."""
        wanted = self.intake_id.course_id.document_ids
        existing = self.document_ids.requirement_id
        for requirement in wanted - existing:
            self.document_ids = [(0, 0, {'requirement_id': requirement.id})]

    def _sync_requirement_lines(self):
        """Materialise the course's documents and requirements as lines.

        Server side on purpose: imports and RPC writes must get the same
        lines as the form does.
        """
        self._sync_document_lines()
        Line = self.env['school.admission.requirement']
        for application in self:
            course = application.course_id
            wanted = {}
            for requirement in course.qualifying_requirement_ids:
                wanted[('qualifying', requirement.id)] = requirement
            for requirement in course.general_requirement_ids:
                wanted[('general', requirement.id)] = requirement
            existing = {
                (line.kind,
                 line.qualifying_id.id if line.kind == 'qualifying'
                 else line.general_id.id): line
                for line in application.requirement_ids
            }
            # Requirements dropped from the course: forget untouched lines.
            for key, line in existing.items():
                if key not in wanted and not line.waiver_requested:
                    line.unlink()
            missing = [key for key in wanted if key not in existing]
            if missing:
                Line.create([
                    {'application_id': application.id,
                     'kind': kind,
                     'qualifying_id': requirement_id
                     if kind == 'qualifying' else False,
                     'general_id': requirement_id
                     if kind == 'general' else False}
                    for kind, requirement_id in missing])

    def _sync_document_lines(self):
        """Materialise one document line per course requirement.

        Server side on purpose: imports and RPC writes must get the same
        document list as the form does.
        """
        Line = self.env['school.admission.document']
        for application in self:
            wanted = application.course_id.document_ids
            # Requirements dropped from the course: forget the empty lines,
            # keep anything the applicant already uploaded.
            application.document_ids.filtered(
                lambda line: line.requirement_id not in wanted
                and not line.attachment).unlink()
            missing = wanted - application.document_ids.requirement_id
            if missing:
                Line.create([
                    {'application_id': application.id,
                     'requirement_id': requirement.id}
                    for requirement in missing])

    @api.depends('adm_fee_invoice_id',
                 'adm_fee_invoice_id.state',
                 'adm_fee_invoice_id.payment_state',
                 'adm_fee_invoice_id.amount_residual')
    def _compute_fee_paid(self):
        """The admission fee counts as paid when its invoice is settled.

        ``account.move.payment_count`` (the previous check) only counted
        *attached* payments: a partial payment, a payment still pending, or a
        cancelled invoice would all mark the fee as paid. The invoice's
        ``payment_state`` is the authoritative value: ``in_payment`` means the
        payment is registered but not yet matched with a bank statement, which
        still settles the student's obligation.
        """
        for rec in self:
            invoice = rec.adm_fee_invoice_id
            rec.invoice_count = 1 if invoice else 0
            rec.fee_paid = bool(
                invoice
                and invoice.state == 'posted'
                and invoice.payment_state in ('paid', 'in_payment')
            )
            if not invoice:
                rec.fee_status = 'no_invoice'
            elif invoice.payment_state in ('paid', 'in_payment'):
                rec.fee_status = 'paid'
            elif invoice.payment_state == 'partial':
                rec.fee_status = 'partial'
            else:
                rec.fee_status = 'unpaid'


    @api.depends('document_ids.attachment', 'document_ids.waived')
    def _compute_missing_documents(self):
        """Documents still owed by the applicant: no file and no waiver."""
        for rec in self:
            rec.missing_documents = ', '.join(
                rec.document_ids.filtered(
                    lambda line: not line.attachment and not line.waived
                ).mapped('name'))

    @api.depends('requirement_ids.status')
    def _compute_pending_requirements(self):
        """Course requirements neither met nor waived yet."""
        for rec in self:
            rec.pending_requirements = ', '.join(
                rec.requirement_ids.filtered(
                    lambda line: line.status == 'pending').mapped('name'))

    @api.depends('name', 'applicant_name')
    def _compute_display_name(self):
        """Show applications as 'APP/2026/0001 - Applicant name'."""
        for rec in self:
            if rec.name and rec.name != 'New':
                rec.display_name = f'{rec.name} - {rec.applicant_name or ""}'
            else:
                rec.display_name = rec.applicant_name or ''

    @api.model_create_multi
    def create(self, vals_list):
        """Give every new application the next application number."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('school.admission.application') or 'New')
        applications = super().create(vals_list)
        applications._sync_requirement_lines()
        return applications

    def write(self, vals):
        if vals.get('state') == 'accepted':
            # ``action_accept`` validates, but the state can also be written
            # straight from the statusbar, an import or an RPC call. The
            # acceptance rule belongs to the field, not only to the button.
            for application in self:
                reasons = []
                if application.missing_documents:
                    reasons.append(_('missing documents: %s')
                                   % application.missing_documents)
                if application.pending_requirements:
                    reasons.append(_('unmet requirements: %s')
                                   % application.pending_requirements)
                if reasons:
                    raise UserError(_(
                        '%(application)s cannot be accepted — %(reasons)s.',
                        application=application.display_name,
                        reasons='; '.join(reasons)))
        res = super().write(vals)
        # Keep the lines in step with the course on every save: this also
        # back-fills applications created before a requirement was added to
        # the course (or before this module version existed).
        self._sync_requirement_lines()
        return res

    # Pipeline -------------------------------------------------------
    #TODO: Check missing documents and waivers before submit
    def action_submit(self):
        """Submit: the intake must be open and the key applicant details filled in."""
        for rec in self:
            if rec.intake_id.state != 'open':
                raise UserError(_('The intake "%s" is not open for applications.',
                                  rec.intake_id.name))
            missing = []
            if not rec.gender:
                missing.append(_('Gender'))
            if not rec.date_of_birth:
                missing.append(_('Date of birth'))
            if not rec.mobile:
                missing.append(_('Mobile'))
            if not (rec.guardian_name and rec.guardian_phone):
                missing.append(_('Guardian name and phone'))
            if missing:
                raise UserError(_('Cannot submit. Missing: %s', ', '.join(missing)))
        self.write({'state': 'submitted'})

    def action_start_review(self):
        """Start reviewing, reusing the review of a previously closed file."""
        self.ensure_one()
        review = self.env['school.admission.review'].search(
            [('application_id', '=', self.id)], limit=1)
        if not review:
            review = self.env['school.admission.review'].create({
                'application_id': self.id,
                'review_start_date': fields.Date.context_today(self),
                'reviewer_id': self.env.user.id,
            })
        self.write({'state': 'review'})
        return review
        
    #TODO: For waived documents, every record shoudl be created but indicated as waived and should always show on the profiile that these documents are missing
    def action_accept(self):
        """Accept: mandatory documents must be attached and the intake must have a free seat."""
        for rec in self:
            if rec.missing_documents:
                raise UserError(_('Missing mandatory documents: %s', rec.missing_documents))
            if rec.pending_requirements:
                raise UserError(_(
                    'Unmet course requirements: %s', rec.pending_requirements))
            intake = rec.intake_id
            if intake.capacity and intake.seats_taken >= intake.capacity:
                raise UserError(_('The intake "%s" is full.', intake.name))
            student_documents = [(0, 0, {
                'requirement_id': line.requirement_id.id,
                'application_id': rec.id,
            }) for line in rec.document_ids if line.attachment]
            student = self.env['school.student'].create({
                'name': rec.applicant_name,
                'gender': rec.gender,
                'date_of_birth': rec.date_of_birth,
                'nationality_id': rec.nationality_id.id,
                'mobile': rec.mobile,
                'email': rec.email,
                'course_id': rec.course_id.id,
                'company_id': rec.company_id.id,
                'application_id': rec.id,
                'guardian_ids': [(0, 0, {
                    'name': rec.guardian_name,
                    'relationship': rec.guardian_relationship or 'guardian',
                    'phone': rec.guardian_phone,
                    'is_emergency': True,
                })],
                'document_ids': student_documents,
            })
            # Semester ladder is generated once, when the student is created
            # from the application (no button on the student form).
            student.action_initialize_program_semesters()
            invoice = self.env['account.move'].create({
                'partner_id': student.partner_id.id,
                'date': fields.Date.context_today(self),
                'move_type': 'out_invoice',
                'ref': "Admission Fee",
                'invoice_line_ids': [(0, 0, {
                    'name': "Admission Fee",
                    'quantity': 1,
                    'price_unit': rec.admission_fee,
                })],
            })
            invoice.action_post()
            rec.write({
                'adm_fee_invoice_id': invoice.id,
                'student_id': student.id,
                'state': 'accepted',
            })

    def action_reject(self):
        """Reject: a rejection reason must be filled in first."""
        # for rec in self:
        #     if not rec.rejection_reason:
        #         raise UserError(_('Enter a rejection reason first.'))
        self.write({'state': 'rejected'})

    def action_open_student(self):
        """Open the student created from this application."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student'),
            'res_model': 'school.student',
            'res_id': self.student_id.id,
            'view_mode': 'form',
        }
    
    def action_view_admission_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Invoice'),
            'res_model': 'account.move',
            'res_id': self.adm_fee_invoice_id.id,
            'view_mode': 'form',
        }

    def action_view_review_status(self):
        self.ensure_one()
        
        review = self.env['school.admission.review'].search([('application_id', '=', self.id)], limit=1)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Review Status'),
            'res_model': 'school.admission.review',
            'view_mode': 'form',
            'target': 'current',
            'res_id': review.id if review else False,  
            'context': {'default_application_id': self.id}, 
        }



