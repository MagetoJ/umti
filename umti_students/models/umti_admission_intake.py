from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolAdmissionIntake(models.Model):
    _name = 'school.admission.intake'
    _description = 'Admission Intake'
    _inherit = ['mail.thread']
    _order = 'date_open desc, id desc'

    name = fields.Char(required=True, tracking=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True,
        tracking=True, ondelete='restrict')
    #TODO: Rethink if we really need to link an intake with a semester
    semester_id = fields.Many2one(
        'umti.academic.term', string='Semester', tracking=True,
        ondelete='restrict', domain="[('academic_year_id', '=', academic_year_id)]",
        help="First term of the cohort. Filled automatically when a rolling "
             "intake is opened.")
    course_id = fields.Many2one(
        'umti.course', required=True, tracking=True, ondelete='restrict')
    department_id = fields.Many2one(
        related='course_id.department_id', store=True, readonly=True)
    show_course_setup_warning = fields.Boolean(
        compute='_compute_course_setup_warning')
    course_setup_warning_message = fields.Char(
        compute='_compute_course_setup_warning')
    date_open = fields.Date(string='Applications Open', required=True)
    date_close = fields.Date(string='Applications Close', required=True)
    start_date = fields.Date(
        string='Course Start', tracking=True,
        help="First day of teaching for this intake. Rolling intakes use "
             "this date to generate their terms.")
    end_date = fields.Date(
        string='Course End', tracking=True,
        help="Leave empty to use the course duration.")
    capacity = fields.Integer(help='Maximum number of admitted students. 0 means unlimited.', compute='_compute_counts')
    admission_fee = fields.Monetary(currency_field='currency_id', compute='_compute_requirements')
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'), ('open', 'Open'),
        ('closed', 'Closed'), ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    application_ids = fields.One2many('school.admission.application', 'intake_id')
    application_count = fields.Integer(compute='_compute_counts')
    seats_taken = fields.Integer(compute='_compute_counts')
    seats_left = fields.Integer(compute='_compute_counts')
    required_document_ids = fields.Many2many("umti.course.required.documents", string="Mandatory Documents", compute="_compute_requirements")
    qualifying_requirement_ids = fields.Many2many("umti.course.qualifying.requirement", string="Mandatory Requirements", compute="_compute_requirements")
    general_requirement_ids = fields.Many2many("umti.course.general.requirement", string="General requirements", compute="_compute_requirements")

    @api.depends('course_id', 'academic_year_id', 'semester_id')
    def _compute_requirements(self):
        for rec in self:
            if not rec.course_id:
                rec.admission_fee = 0
                rec.required_document_ids = False
                rec.qualifying_requirement_ids = False
                rec.general_requirement_ids = False
                continue  # Skip to the next record immediately
            
            # 2. Map course requirements directly
            rec.qualifying_requirement_ids = rec.course_id.qualifying_requirement_ids
            rec.general_requirement_ids = rec.course_id.general_requirement_ids
            rec.required_document_ids = rec.course_id.document_ids

            # 3. Use the same fee lines the intake invoice will use.
            fee_lines = self.env['umti.fee.structure.line']._applicable_lines(
                rec.course_id, rec.academic_year_id, rec.semester_id)
            admission_line = fee_lines.filtered(
                lambda line: line.votehead.code == 'ADMISSION')[:1]
            rec.admission_fee = admission_line.amount if admission_line else 0





    @api.depends('capacity', 'application_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.capacity = rec.course_id.course_capacity if rec.course_id else 0 
            apps = rec.application_ids
            rec.application_count = len(apps)
            rec.seats_taken = len(apps.filtered(
                lambda a: a.state in ('accepted', 'enrolled')))
            rec.seats_left = (rec.capacity - rec.seats_taken) if rec.capacity else 0

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        if self.semester_id and self.semester_id.academic_year_id != self.academic_year_id:
            self.semester_id = False

    @api.constrains('academic_year_id', 'semester_id')
    def _check_semester_in_year(self):
        for rec in self:
            if (rec.semester_id
                    and rec.semester_id.academic_year_id != rec.academic_year_id):
                raise ValidationError(_('The semester does not belong to the selected academic year.'))

    @api.constrains('date_open', 'date_close')
    def _check_dates(self):
        for rec in self:
            if rec.date_close < rec.date_open:
                raise ValidationError(_('The closing date cannot be before the opening date.'))

    @api.constrains('start_date', 'end_date')
    def _check_course_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_(
                    'The course end date cannot be before its start date.'))

    @api.constrains('academic_year_id', 'start_date')
    def _check_start_in_academic_year(self):
        for rec in self:
            year = rec.academic_year_id
            if (rec.start_date and year
                    and not (year.start_date <= rec.start_date <= year.end_date)):
                raise ValidationError(_(
                    "The course start date must fall inside the intake's "
                    "academic year %(year)s.", year=year.name))

    @api.depends('course_id',
                 'course_id.document_ids',
                 'course_id.qualifying_requirement_ids',
                 'course_id.general_requirement_ids',
                 'course_id.requirements_warning_dismissed')
    def _compute_course_setup_warning(self):
        for rec in self:
            course = rec.course_id
            rec.show_course_setup_warning = bool(
                course and course.show_setup_warning)
            rec.course_setup_warning_message = (
                course.setup_warning_message if course else False)

    def action_dismiss_course_setup_warning(self):
        self.mapped('course_id').action_dismiss_setup_warning()

    def _ensure_terms(self):
        """Create (or fetch) the cohort terms for a rolling intake."""
        self.ensure_one()
        pattern = self.course_id._get_term_pattern()
        if not pattern or pattern.anchor != 'intake':
            return self.env['umti.academic.term']
        existing = self.env['umti.academic.term'].search([
            ('intake_id', '=', self.id),
        ])
        if existing:
            return existing
        if not self.start_date:
            raise UserError(_(
                "Set the course start date on intake %(intake)s before "
                "generating its terms.", intake=self.name))
        terms = self.env['umti.academic.year'].generate_course_terms(
            self.course_id, self.start_date, self.end_date,
            year=self.academic_year_id)
        terms.filtered(lambda term: not term.intake_id).write(
            {'intake_id': self.id})
        if not self.semester_id:
            first = terms.filtered(
                lambda term: not term.parent_term).sorted(
                    'term_start_date')[:1]
            self.semester_id = first
        return terms

    def _reschedule_terms(self):
        """Move the cohort's existing terms when intake dates change."""
        self.ensure_one()
        pattern = (self.course_id._get_term_pattern()
                   if self.course_id else False)
        if not pattern or pattern.anchor != 'intake':
            return
        terms = self.env['umti.academic.term'].search([
            ('intake_id', '=', self.id),
        ])
        if not terms:
            return
        start = self.start_date
        end = self.end_date or self.env['umti.academic.year']._course_end(
            self.course_id, start)
        if not start or not end:
            return
        Year = self.env['umti.academic.year']
        main_lines = pattern._main_lines()
        main_terms = terms.filtered(lambda term: not term.parent_term)
        by_sequence = {term.sequence: term for term in main_terms}
        spans = Year._split_span(main_lines, start, end)
        for line in main_lines:
            term = by_sequence.get(line.sequence)
            if not term:
                continue
            line_start, line_end = spans[line.id]
            term.write({
                'term_start_date': line_start,
                'term_end_date': line_end,
                'name': Year._term_name(self.course_id, line.name, line_start),
            })
            children = pattern._child_lines(line.sequence)
            child_by_sequence = {
                child.sequence: child for child in terms.filtered(
                    lambda child: child.parent_term == term)
            }
            child_spans = Year._split_span(children, line_start, line_end)
            for child in children:
                child_term = child_by_sequence.get(child.sequence)
                if not child_term:
                    continue
                child_start, child_end = child_spans[child.id]
                child_term.write({
                    'term_start_date': child_start,
                    'term_end_date': child_end,
                    'name': Year._term_name(
                        self.course_id, child.name, child_start),
                })

    def _generate_intake_terms(self):
        for rec in self:
            pattern = (rec.course_id._get_term_pattern()
                       if rec.course_id else False)
            if pattern and pattern.anchor == 'intake':
                rec._ensure_terms()

    def write(self, vals):
        opening = vals.get('state') == 'open'
        res = super().write(vals)
        if {'start_date', 'end_date'} & set(vals):
            self._reschedule_terms()
        if opening:
            self._generate_intake_terms()
        return res

    def action_open(self):
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_course(self):
        self.ensure_one()
        if not self.course_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Course'),
            'res_model': 'umti.course',
            'res_id': self.course_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    def action_view_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Applications'),
            'res_model': 'school.admission.application',
            'view_mode': 'list,form',
            'domain': [('intake_id', '=', self.id)],
            'context': {'default_intake_id': self.id},
        }
