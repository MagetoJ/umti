from odoo import api, fields, models, _


class UmtiStudentFinance(models.TransientModel):
    """Filterable control room for the bursar."""

    _name = 'umti.student.finance'
    _description = 'Student Finance'

    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True,
        default=lambda self: self.env['umti.academic.year'].search([
            ('status', '=', 'running'), ('active', '=', True),
        ], order='start_date desc', limit=1))
    course_id = fields.Many2one('umti.course', string='Course')
    intake_id = fields.Many2one('school.admission.intake', string='Intake')
    student_state = fields.Selection([
        ('all', 'All'),
        ('incomplete', 'Incomplete'),
        ('active', 'Active'),
        ('deferred', 'Deferred'),
        ('suspended', 'Suspended'),
        ('graduated', 'Graduated'),
        ('discontinued', 'Discontinued'),
    ], default='active', required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)

    student_count = fields.Integer(compute='_compute_kpis')
    semester_invoice_count = fields.Integer(compute='_compute_kpis')
    draft_invoice_count = fields.Integer(compute='_compute_kpis')
    invoiced_total = fields.Monetary(
        compute='_compute_kpis', currency_field='currency_id')
    paid_total = fields.Monetary(
        compute='_compute_kpis', currency_field='currency_id')
    outstanding_total = fields.Monetary(
        compute='_compute_kpis', currency_field='currency_id')
    payment_count = fields.Integer(compute='_compute_kpis')
    payment_total = fields.Monetary(
        compute='_compute_kpis', currency_field='currency_id')
    paid_count = fields.Integer(compute='_compute_kpis')
    partial_count = fields.Integer(compute='_compute_kpis')
    unpaid_count = fields.Integer(compute='_compute_kpis')
    last_run_summary = fields.Text(readonly=True, copy=False)

    # ------------------------------------------------------------------
    def _student_domain(self):
        self.ensure_one()
        domain = [
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
        ]
        if self.student_state != 'all':
            domain.append(('state', '=', self.student_state))
        if self.course_id:
            domain.append(('course_id', '=', self.course_id.id))
        if self.intake_id:
            domain.append(
                ('application_id.intake_id', '=', self.intake_id.id))
        if self.academic_year_id:
            domain += [
                ('semester_ids.state', '=', 'active'),
                ('semester_ids.academic_year_id', '=',
                 self.academic_year_id.id),
            ]
        return domain

    def _target_students(self):
        self.ensure_one()
        students = self.env['school.student'].search(self._student_domain())
        return students.filtered(self._billing_terms)

    def _billing_terms(self, student):
        """Active semesters in the year, one invoice per term."""
        self.ensure_one()
        return student.semester_ids.filtered(
            lambda semester: semester.state == 'active'
            and semester.academic_year_id == self.academic_year_id
            and semester.academic_term_id
        ).sorted(
            lambda semester: semester.academic_term_id.term_start_date)

    def _invoice_domain(self):
        self.ensure_one()
        students = self._target_students()
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('umti_invoice_kind', '=', 'semester'),
            ('state', '!=', 'cancel'),
            ('umti_student_id', 'in', students.ids),
        ]
        if self.academic_year_id:
            domain.append(
                ('umti_academic_year_id', '=', self.academic_year_id.id))
        if self.course_id:
            domain.append(('umti_course_id', '=', self.course_id.id))
        return domain

    @api.depends('academic_year_id', 'course_id', 'intake_id',
                 'student_state')
    def _compute_kpis(self):
        Move = self.env['account.move']
        Payment = self.env['account.payment']
        for dashboard in self:
            students = dashboard._target_students()
            domain = dashboard._invoice_domain()
            invoices = Move.search(domain)
            posted = invoices.filtered(lambda move: move.state == 'posted')
            drafts = invoices.filtered(lambda move: move.state == 'draft')
            dashboard.student_count = len(students)
            dashboard.semester_invoice_count = len(invoices)
            dashboard.draft_invoice_count = len(drafts)
            dashboard.invoiced_total = sum(posted.mapped('amount_total'))
            outstanding = sum(posted.mapped('amount_residual'))
            dashboard.outstanding_total = outstanding
            dashboard.paid_total = (
                dashboard.invoiced_total - outstanding)
            dashboard.paid_count = len(posted.filtered(
                lambda move: move.payment_state == 'paid'))
            dashboard.partial_count = len(posted.filtered(
                lambda move: move.payment_state in ('partial', 'in_payment')))
            dashboard.unpaid_count = len(posted.filtered(
                lambda move: move.payment_state in ('not_paid', 'blocked')))
            payments = Payment.search([
                ('umti_student_id', 'in', students.ids),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound'),
            ])
            dashboard.payment_count = len(payments)
            dashboard.payment_total = sum(payments.mapped('amount'))

    # ------------------------------------------------------------------
    def action_generate_invoices(self):
        self.ensure_one()
        Line = self.env['umti.fee.structure.line']
        Move = self.env['account.move']
        created = skipped_term = skipped_fee = skipped_existing = 0
        for student in self._target_students():
            semesters = self._billing_terms(student)
            if not semesters:
                skipped_term += 1
                continue
            for semester in semesters:
                term = semester.academic_term_id
                term_invoices = Move.search([
                    ('move_type', '=', 'out_invoice'),
                    ('umti_student_id', '=', student.id),
                    ('umti_academic_term_id', '=', term.id),
                    ('state', '!=', 'cancel'),
                    ('umti_invoice_kind', 'in', ('semester', 'intake')),
                ])
                if term_invoices.filtered(
                        lambda move: move.umti_invoice_kind == 'semester'):
                    skipped_existing += 1
                    continue
                fee_lines = Line._applicable_lines(
                    student.course_id, self.academic_year_id, term,
                    include_paid_once=False, include_refundable=False)
                if not fee_lines:
                    skipped_fee += 1
                    continue
                # Intake used to raise the first term's recurring fees as an
                # "intake" invoice. Adopt such an invoice instead of raising
                # the same fees a second time.
                required = fee_lines.votehead
                recurring_intake = term_invoices.filtered(
                    lambda move: move.umti_invoice_kind == 'intake'
                    and not (required - move.invoice_line_ids.umti_votehead_id)
                    and not move.invoice_line_ids.umti_votehead_id.filtered(
                        lambda votehead: votehead.paid_once
                        or votehead.refundable))
                if recurring_intake:
                    recurring_intake[0].umti_invoice_kind = 'semester'
                    skipped_existing += 1
                    continue
                Move.create({
                    'partner_id': student.partner_id.id,
                    'move_type': 'out_invoice',
                    'date': fields.Date.context_today(self),
                    'ref': _('Semester Fees - %(term)s', term=term.name),
                    'umti_student_id': student.id,
                    'umti_academic_term_id': term.id,
                    'umti_fee_period_sequence': term.sequence,
                    'umti_invoice_kind': 'semester',
                    'invoice_line_ids': [(0, 0, {
                        'name': line.votehead.name,
                        'quantity': 1,
                        'price_unit': line.amount,
                        'umti_votehead_id': line.votehead.id,
                    }) for line in fee_lines.sorted(
                        lambda line: (line.votehead.sequence,
                                      line.votehead.name))],
                })
                created += 1
        drafts = self.env['account.move'].search(
            self._invoice_domain() + [('state', '=', 'draft')])
        drafts.action_post()
        self.last_run_summary = _(
            "Created and posted %(created)d invoice(s); posted %(drafts)d "
            "existing draft(s). Skipped: %(existing)d already invoiced, "
            "%(term)d with no active term, %(fee)d with no recurring fee "
            "lines.",
            created=created, drafts=len(drafts),
            existing=skipped_existing, term=skipped_term, fee=skipped_fee)

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'views': [[
                self.env.ref(
                    'umti_students.umti_student_invoice_view_list').id,
                'list'], [False, 'form']],
            'domain': self._invoice_domain(),
            'context': {'create': False},
        }

    def action_view_payments(self):
        self.ensure_one()
        students = self._target_students()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student Payments'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'views': [[
                self.env.ref(
                    'umti_students.umti_student_payment_view_list').id,
                'list'], [False, 'form']],
            'domain': [('umti_student_id', 'in', students.ids)],
            'context': {'create': False},
        }
