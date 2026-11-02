from dateutil.relativedelta import relativedelta

import logging

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SchoolStudent(models.Model):
    """A student. The contact details live on the linked res.partner (_inherits)."""
    _name = 'school.student'
    _description = 'Student'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'admission_no desc, id desc'
    _rec_names_search = ['name', 'admission_no']
    _inherits = {'res.partner': 'partner_id'}

    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    fee_currency_id = fields.Many2one("res.currency", string="Fee Currency", default=lambda self: self.env.company.currency_id)

    # Computed financial fields. Not stored on purpose: nothing that moves
    # money (posting an invoice, registering a payment) could invalidate a
    # stored value, so it would be computed once at creation and stay stale.
    total_charged = fields.Monetary(
        string="Total Charged",
        currency_field="fee_currency_id",
        compute="_compute_financial_totals",
    )
    total_paid = fields.Monetary(
        string="Total Paid",
        currency_field="fee_currency_id",
        compute="_compute_financial_totals",
    )
    balance = fields.Monetary(
        string="Balance Due",
        currency_field="fee_currency_id",
        compute="_compute_financial_totals",
    )

    partner_id = fields.Many2one(
        'res.partner', string='Contact', required=True,
        ondelete='restrict', auto_join=True, index=True)

    admission_no = fields.Char(
        string='Admission No', required=True, copy=False, readonly=True,
        index=True, default='New', tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one(
        'res.users', string='Related User', copy=False,
        help='Portal or internal user used by the student to log in.')
        
    state = fields.Selection([
        ('incomplete', 'Incomplete'),
        ('active', 'Active'),
        ('deferred', 'Deferred'),
        ('suspended', 'Suspended'),
        ('graduated', 'Graduated'),
        ('discontinued', 'Discontinued'),
    ], default='incomplete', required=True, tracking=True, copy=False)
    fee_status = fields.Selection([
        ('self', 'Self-paying'),
        ('sponsored', 'Sponsored'),
    ], string='Fee Status', default='self', required=True, tracking=True)
    sponsor_id = fields.Many2one('res.partner', string='Sponsor')

    has_hold = fields.Boolean(
        string='On Hold', tracking=True, copy=False,
        groups='umti_students.group_umti_students_admin',
        help="An administrator must clear this before the student can "
             "graduate. It is raised automatically when a semester is left "
             "open because of failed or incomplete unit results, and can "
             "also be set by hand (unpaid fees, disciplinary cases).")

    gender = fields.Selection([
        ('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    date_of_birth = fields.Date(tracking=True)
    age = fields.Integer(compute='_compute_age')
    nationality_id = fields.Many2one('res.country', string='Nationality')

    course_id = fields.Many2one(
        'umti.course', string='Course', tracking=True, ondelete='restrict')
    department_id = fields.Many2one(
        related='course_id.department_id', store=True, readonly=True)

    po_box = fields.Char(string='P.O. Box')
    county = fields.Char()

    medical_card_no = fields.Char(string='Medical Card No')
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'), ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'), ('o+', 'O+'), ('o-', 'O-')])
    medical_conditions = fields.Text()

    guardian_ids = fields.One2many('school.student.guardian', 'student_id')
    document_ids = fields.One2many('school.student.document', 'student_id', readonly=True)
    lending_ids = fields.One2many('umti.library.lending', 'student_id', readonly=True)
    kit_ids = fields.One2many("umti.kit.issuance", "student_id", readonly=True)
    semester_ids = fields.One2many('umti.student.semester', 'student_id', readonly=True)
    student_student_fee_record_ids = fields.Many2many(
        'account.move', 'school_student_fee_move_rel', 'student_id', 'move_id',
        string='Fee Invoices', compute='_compute_fee_records')
    student_payment_record_ids = fields.Many2many(
        'account.payment', 'school_student_payment_rel', 'student_id',
        'payment_id', string='Fee Payments', compute='_compute_fee_records')
    fee_record_ids = fields.One2many(
        'umti.fee.record', 'student_id', string='Fee Ledger')
    invoices_count = fields.Integer(compute='_compute_fee_records')
    payments_count = fields.Integer(compute='_compute_fee_records')
    unpaid_lost_books_count = fields.Integer(compute='_compute_fee_records')
    unpaid_lost_kits_count = fields.Integer(compute='_compute_fee_records')
    unit_ids = fields.One2many('umti.course.units', compute='_compute_unit_ids')

    @api.depends('partner_id')
    def _compute_financial_totals(self):
        """Calculates total invoiced (total_charged) and total payments received (total_paid)

        filters posted customer invoices/credit notes and posted payments matched to student partner.
        """
        for student in self:
            if not student.partner_id:
                student.total_charged = 0.0
                student.total_paid = 0.0
                student.balance = 0.0
                continue

            # Fetch posted customer invoices and credit notes for the linked partner
            invoices = self.env['account.move'].search([
                ('partner_id', '=', student.partner_id.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted')
            ])
            
            # Sum up posted customer invoices (subtract refunds if any)
            # amount_total_signed already carries the sign of the move type
            # (refunds are negative), so both types are added as they are.
            total_charged = sum(inv.amount_total_signed for inv in invoices)

            # Fetch posted customer payments for the linked partner
            payments = self.env['account.payment'].search([
                ('partner_id', '=', student.partner_id.id),
                ('payment_type', '=', 'inbound'),
                ('state', '=', 'posted')
            ])
            total_paid = sum(payments.mapped('amount'))

            student.total_charged = total_charged
            student.total_paid = total_paid
            student.balance = total_charged - total_paid
        

    _sql_constraints = [
        ('admission_no_uniq', 'unique(admission_no)',
         'The admission number must be unique.'),
    ]
    @api.depends('course_id')
    def _compute_unit_ids(self):
        for rec in self:
            rec.unit_ids = rec.course_id.unit_ids


    @api.depends('date_of_birth')
    def _compute_age(self):
        """Age in whole years today, 0 when the date of birth is unknown."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.age = (relativedelta(today, rec.date_of_birth).years
                       if rec.date_of_birth else 0)

   

    @api.depends('name', 'admission_no')
    def _compute_display_name(self):
        """Show students as [ADM/2026/0001] Name once the number is assigned."""
        for rec in self:
            if rec.admission_no and rec.admission_no != 'New':
                rec.display_name = f'[{rec.admission_no}] {rec.name or ""}'
            else:
                rec.display_name = rec.name or ''
                
    @api.depends('partner_id')
    def _compute_fee_records(self):
        for rec in self:
            if rec.partner_id:
                fee_records = self.env['account.move'].search([('partner_id', '=', rec.partner_id.id)])
                payment_records = self.env['account.payment'].search([('partner_id', '=', rec.partner_id.id)])
                unpaid_lost_books = self.env['umti.library.lending'].search([('student_id', '=', rec.id),('state', '=', 'lost')])
                unpaid_lost_kits = self.env['umti.kit.issuance'].search([('student_id', '=', rec.id),('state', '=', 'lost')])
                rec.unpaid_lost_books_count = len(unpaid_lost_books)
                rec.unpaid_lost_kits_count = len(unpaid_lost_kits)
                rec.invoices_count = len(fee_records)
                rec.payments_count = len(payment_records)
                rec.student_payment_record_ids = [Command.set(payment_records.ids)]
                rec.student_student_fee_record_ids = [Command.set(fee_records.ids)]
            else:
                rec.student_payment_record_ids = [Command.clear()]
                rec.student_student_fee_record_ids = [Command.clear()]


    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        """A student cannot be born in the future."""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_of_birth and rec.date_of_birth > today:
                raise ValidationError(_('Date of birth cannot be in the future.'))

    @api.model_create_multi
    def create(self, vals_list):
        """Give every new student the next admission number from the sequence."""
        for vals in vals_list:
            if vals.get('admission_no', 'New') == 'New':
                vals['admission_no'] = (
                    self.env['ir.sequence'].next_by_code('school.student') or 'New')
        return super().create(vals_list)

    def _check_ready_to_activate(self):
        """Raise a UserError listing what is still missing before a student can be activated."""
        for rec in self:
            missing = []
            if not rec.gender:
                missing.append(_('Gender'))
            if not rec.date_of_birth:
                missing.append(_('Date of birth'))
            if not rec.mobile:
                missing.append(_('Mobile'))
            if not rec.course_id:
                missing.append(_('Course'))
            if not rec.guardian_ids.filtered('is_emergency'):
                missing.append(_('At least one emergency contact'))
            if rec.fee_status == 'sponsored' and not rec.sponsor_id:
                missing.append(_('Sponsor'))
            if missing:
                raise UserError(_(
                    '%(student)s cannot be activated. Missing: %(fields)s',
                    student=rec.name, fields=', '.join(missing)))

    # Status changes ------------------------------------------------
    def action_activate(self):
        """Mark the student Active, after checking the profile is complete."""
        self._check_ready_to_activate()
        
        portal_group = self.env.ref('base.group_portal')
        
        user =self.env['res.users'].create({
            'name': self.name,
            'login': self.email or self.name, 
            'email': self.email,
            'share': True,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'groups_id': [(6, 0, [portal_group.id])], 
        })

        #TODO: Trigger an invitation email to be sent after the user has been created
        self.write({'user_id': user.id})        
        self.write({'state': 'active'})


    def action_initialize_program_semesters(self):
        """Generate the student's semester ladder from the course period.

        Runs automatically when a student is created from an admission
        application; there is no button for it. Idempotent: a student that
        already has semesters is left untouched.
        """
        self.ensure_one()
        if self.semester_ids:
            return
        course_period = self.course_id.period if self.course_id.period else 0
        if not course_period:
            # Automatic call: do not block the admission flow on a missing
            # course configuration, just leave the student without semesters.
            _logger.warning(
                "Semesters not generated for %s: course period is not set.",
                self.display_name)
            return

        # 1. How many semesters a year holds is decided in one place, shared
        # with the semester label.
        terms_per_year = self.env[
            'umti.student.semester']._semesters_per_year()

        semester_ids = []
        sequence_counter = 1

        # 2. Outer Loop: Iterates through each Year (e.g., Year 1, Year 2...)
        for year_idx in range(course_period):
            year_num = year_idx + 1

            # 3. Inner Loop: Generates the semesters of that specific year
            for _term_idx in range(terms_per_year):
                semester = self.env['umti.student.semester'].create({
                    'student_id': self.id,
                    'course_year': year_num,
                    'sequence': sequence_counter,
                    'company_id': self.company_id.id,
                })
                semester_ids.append(semester.id)
                sequence_counter += 1
                
        # 5. Safe batch writing outside loop logic
        if semester_ids:
            self.write({'semester_ids': [(6, 0, semester_ids)]})

        #update academic year and term with the current active academic year and its running term
        current_academic_year = self.env['umti.academic.year'].search([('status', '=', 'running'),('active', '=', True)],limit=1)
        if current_academic_year:
            running_term = current_academic_year.academic_term_ids.filtered(
                lambda t: t.status == 'in_progress' and not t.parent_term)[:1]
            first_semester = self.semester_ids.sorted('sequence')[:1]
            first_semester.academic_year_id = current_academic_year.id
            if running_term:
                first_semester.academic_term_id = running_term
            first_semester.write({'state': 'active'})

        
                

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {'default_partner_id': self.partner_id.id},
        }
    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payments',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {'default_partner_id': self.partner_id.id},
        }
    def action_view_lost_books(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lost Books',
            'res_model': 'umti.library.lending',
            'view_mode': 'list,form',
            'domain': [('state', '=', 'lost'),('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
    def action_view_lost_kits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lost Kits',
            'res_model': 'umti.kit.issuance',
            'view_mode': 'list,form',
            'domain': [('state', '=', 'lost'),('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_defer(self):
        self.write({'state': 'deferred'})

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_graduate(self):
        # Hook: graduation checks (minimum units, attendance, fee completion)
        # belong to the enrollment, attendance and finance modules.
        on_hold = self.filtered('has_hold')
        if on_hold:
            raise UserError(_(
                "%(students)s is on hold. An administrator must resolve the "
                "hold before the student can graduate.",
                students=', '.join(on_hold.mapped('display_name'))))
        self.write({'state': 'graduated'})

    def action_discontinue(self):
        self.write({'state': 'discontinued'})

    def action_set_incomplete(self):
        self.write({'state': 'incomplete'})

    # ------------------------------------------------------------------
    # Holds
    # ------------------------------------------------------------------
    def _hold_blockers(self):
        """Reasons the hold cannot be cleared yet, one line each.

        A hold may be manual (fees, discipline), in which case there is no
        blocker and the administrator simply clears it. When it was raised
        by an open semester, that semester's results must be clean first.
        """
        self.ensure_one()
        blockers = []
        for semester in self.semester_ids.filtered(
                lambda s: s.state == 'active'):
            state = semester._results_state()
            label = semester.name or _('Semester %s', semester.sequence)
            if state['missing']:
                blockers.append(_(
                    "%(semester)s has no unit results recorded.",
                    semester=label))
            if state['failed']:
                blockers.append(_(
                    "%(semester)s has failed units: %(units)s.",
                    semester=label,
                    units=', '.join(state['failed'].mapped(
                        'unit_id.display_name'))))
            if state['incomplete']:
                blockers.append(_(
                    "%(semester)s has results not yet finalised: %(units)s.",
                    semester=label,
                    units=', '.join(state['incomplete'].mapped(
                        'unit_id.display_name'))))
        return blockers

    def action_resolve_hold(self):
        """Administrator: clear the hold once its reason is gone.

        Open semesters are closed at the same time, because the hold is what
        kept them open.
        """
        self.ensure_one()
        blockers = self._hold_blockers()
        if blockers:
            raise UserError(_(
                "The hold on %(student)s cannot be cleared yet:\n\n"
                "%(blockers)s\n\n"
                "Fix the unit results in Exams \u25b8 Unit Results (enter or "
                "correct the marks, then publish the result). When every "
                "open semester is clean, press Resolve Hold again.",
                student=self.display_name,
                blockers='\n'.join('\u2022 ' + line for line in blockers)))
        open_semesters = self.semester_ids.filtered(
            lambda s: s.state == 'active')
        open_semesters.write({'state': 'complete'})
        self.has_hold = False
        self.message_post(body=_(
            "Hold cleared by %(user)s.", user=self.env.user.name))
        return True

