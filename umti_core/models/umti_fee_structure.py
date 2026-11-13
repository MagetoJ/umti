# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UmtiFeeStructure(models.Model):
    _name = 'umti.fee.structure'
    _description = 'Umti Fee Structure'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='Name', compute='_compute_name', store=True, readonly=True,
        tracking=True)
    status = fields.Selection([
        ('proposed', 'Proposed'),
        ('active', 'Active'),
        ('historic', 'Historic'),
    ], default='proposed', string="Status", tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    active_from = fields.Date(
        string='Active From', tracking=True,
        default=fields.Date.context_today)
    active_to = fields.Date(string='Active To', tracking=True)
    close_date = fields.Date(string='Closed On', readonly=True, copy=False,
                             tracking=True)
    academic_year_ids = fields.Many2many(
        'umti.academic.year', 'umti_fee_structure_academic_year_rel',
        'structure_id', 'academic_year_id', string='Academic Years',
        compute='_compute_academic_year_ids', store=True, readonly=True)
    structure_line_ids = fields.One2many('umti.fee.structure.line', 'structure_id', string="Structure Lines")
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)

    @api.depends('status', 'company_id', 'company_id.name',
                 'active_from', 'active_to')
    def _compute_name(self):
        labels = {
            'proposed': _('Proposed'),
            'active': _('Active'),
            'historic': _('Historic'),
        }
        for structure in self:
            state = labels.get(structure.status, '')
            if structure.active_from and structure.active_to:
                period = " (%s - %s)" % (
                    structure.active_from.strftime('%d %b %Y'),
                    structure.active_to.strftime('%d %b %Y'))
            elif structure.active_from:
                period = " (from %s)" % structure.active_from.strftime(
                    '%d %b %Y')
            elif structure.active_to:
                period = " (until %s)" % structure.active_to.strftime(
                    '%d %b %Y')
            else:
                period = ''
            if structure.company_id:
                structure.name = _(
                    "%(state)s Fee Structure for %(company)s%(period)s",
                    state=state, company=structure.company_id.name,
                    period=period)
            else:
                structure.name = _(
                    "%(state)s Fee Structure%(period)s",
                    state=state, period=period)

    @api.depends('structure_line_ids.academic_year_ids',
                 'active_from', 'active_to')
    def _compute_academic_year_ids(self):
        Year = self.env['umti.academic.year']
        for structure in self:
            years = structure.structure_line_ids.mapped('academic_year_ids')
            domain = [('active', '=', True)]
            if structure.active_from:
                domain.append(('end_date', '>=', structure.active_from))
            if structure.active_to:
                domain.append(('start_date', '<=', structure.active_to))
            if structure.active_from or structure.active_to:
                years |= Year.search(domain)
            structure.academic_year_ids = years

    @api.constrains('active_from', 'active_to')
    def _check_active_dates(self):
        for structure in self:
            if (structure.active_from and structure.active_to
                    and structure.active_to < structure.active_from):
                raise ValidationError(_(
                    'Active To cannot be before Active From.'))

    def write(self, vals):
        if vals.get('status') == 'historic' and not vals.get('close_date'):
            vals = dict(
                vals, close_date=fields.Date.context_today(self))
        elif vals.get('status') in ('proposed', 'active'):
            vals = dict(vals, close_date=False)
        return super().write(vals)

    @api.model
    def _get_current(self, company):
        """The structure in force for a company: active, else proposed."""
        domain = [('company_id', '=', company.id), ('active', '=', True)]
        structure = self.search(
            domain + [('status', '=', 'active')],
            order='active_from desc, id desc', limit=1)
        if not structure:
            structure = self.search(
                domain + [('status', '=', 'proposed')],
                order='active_from desc, id desc', limit=1)
        return structure

    def _fee_years(self):
        self.ensure_one()
        years = self.academic_year_ids
        if not years:
            year = self.env['umti.academic.year'].search([
                ('status', '=', 'running'), ('active', '=', True),
            ], order='start_date desc', limit=1)
            years = year
        return years

    def _ensure_lines_for_course(self, course):
        """Make sure each votehead covers a course with the default amount."""
        self.ensure_one()
        years = self._fee_years()
        if not years:
            return self.env['umti.fee.structure.line']
        courses = self.env['umti.course'].search([
            ('active', '=', True),
            ('status', '!=', 'discontinued'),
            ('company_id', 'in', [self.company_id.id, False]),
        ])
        departments = courses.mapped('department_id')
        voteheads = self.env['umti.structure.votehead'].search([
            ('active', '=', True),
            ('company_id', 'in', [self.company_id.id, False]),
        ])
        other_courses = courses - course
        created = self.env['umti.fee.structure.line']
        for votehead in voteheads:
            lines = self.structure_line_ids.filtered(
                lambda line: line.votehead == votehead)
            default = lines.filtered(
                lambda line: not line.course_ids
                or (other_courses and other_courses <= line.course_ids))[:1]
            if default:
                vals = {}
                if course not in default.course_ids:
                    vals['course_ids'] = [(4, course.id)]
                if (course.department_id
                        and course.department_id not in default.department_ids):
                    vals['department_ids'] = [(4, course.department_id.id)]
                if vals:
                    default.write(vals)
                continue
            if lines and course in lines.mapped('course_ids'):
                continue
            created |= self.env['umti.fee.structure.line'].create({
                'structure_id': self.id,
                'course_ids': [(6, 0, courses.ids)],
                'academic_year_ids': [(6, 0, years.ids)],
                'department_ids': [(6, 0, departments.ids)],
                'votehead': votehead.id,
                'period_sequence': 0,
                'amount': 0,
                'currency_id': self.company_id.currency_id.id,
                'company_id': self.company_id.id,
            })
        return created

    def action_fill_from_voteheads(self):
        for structure in self:
            courses = self.env['umti.course'].search([
                ('active', '=', True),
                ('status', '!=', 'discontinued'),
                ('company_id', 'in', [structure.company_id.id, False]),
            ])
            for course in courses:
                structure._ensure_lines_for_course(course)

    def approve_fee_structure(self):
        for structure in self:
            if not structure.structure_line_ids:
                raise UserError(_('Fee Structure Lines are not set.'))
            structure.write({'status': 'active'})

    def close_fee_structure(self):
        self.write({
            'status': 'historic',
            'close_date': fields.Date.context_today(self),
        })

class UmtiStructureVotehead(models.Model):
    _name = 'umti.structure.votehead'
    _description = 'Umti Structure Votehead'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    paid_once = fields.Boolean(
        string='Paid Once', tracking=True,
        help="Charge this votehead only once, normally on the intake "
             "invoice; semester invoices must skip it.")
    refundable = fields.Boolean(
        string='Refundable on Graduation', tracking=True,
        help="A credit note against the intake invoice can refund this "
             "votehead when the student graduates.")
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


class UmtiFeeStructureLine(models.Model):
    _name = 'umti.fee.structure.line'
    _description = 'Umti Fee Structure Line'
    _rec_name = 'votehead'

    academic_year_ids = fields.Many2many(
        'umti.academic.year', 'umti_fee_structure_line_academic_year_rel',
        'line_id', 'academic_year_id', string='Academic Years',
        required=True)
    semester_ids = fields.Many2many(
        'umti.academic.term', 'umti_fee_structure_line_term_rel',
        'line_id', 'term_id', string='Semesters')
    course_ids = fields.Many2many(
        'umti.course', 'umti_fee_structure_line_course_rel',
        'line_id', 'course_id', string='Courses', required=True)
    department_ids = fields.Many2many(
        'umti.department', 'umti_fee_structure_line_department_rel',
        'line_id', 'department_id', string='Departments', required=True)
    period_sequence = fields.Integer(
        string='Term Period', default=0,
        compute='_compute_period_sequence', store=True, readonly=False,
        help="Sequence of the pattern line this fee applies to (10, 20, "
             "...). Use this instead of a concrete term so every intake of "
             "a rolling course uses the same fee line. 0 applies to any "
             "period.")
    structure_id = fields.Many2one(
        'umti.fee.structure', string="Structure", required=True)
    votehead = fields.Many2one(
        'umti.structure.votehead', string="Voteheads", required=True)
    amount = fields.Monetary(
        string="Amount", required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string="Currency", required=True,
        default=lambda self: self.env.user.company_id.currency_id)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.user.company_id)

    def _specificity(self):
        """Lower means a more specific line for the same votehead."""
        self.ensure_one()
        return (
            0 if self.semester_ids else 1,
            0 if self.period_sequence else 1,
            len(self.course_ids),
            len(self.academic_year_ids),
            len(self.department_ids),
        )

    @api.model
    def _applicable_lines(self, course, year=None, term=None,
                          include_paid_once=True, include_refundable=True):
        """Lines for an invoice.

        Pass ``include_paid_once=False`` and ``include_refundable=False``
        for semester invoices: one-time and refundable voteheads belong on
        the intake invoices only.
        """
        structure = self.env['umti.fee.structure']._get_current(
            course.company_id)
        if not structure:
            return self.browse()
        lines = structure.structure_line_ids.filtered(
            lambda line: line.active and line.amount
            and course in line.course_ids
            and (include_paid_once or not line.votehead.paid_once)
            and (include_refundable or not line.votehead.refundable))
        if year:
            lines = lines.filtered(
                lambda line: not line.academic_year_ids
                or year in line.academic_year_ids)
        if term:
            lines = lines.filtered(
                lambda line: not line.semester_ids
                or term in line.semester_ids)
            lines = lines.filtered(
                lambda line: line.period_sequence in (0, term.sequence))
        chosen = {}
        for line in lines:
            current = chosen.get(line.votehead.id)
            if not current or line._specificity() < current._specificity():
                chosen[line.votehead.id] = line
        return self.browse([line.id for line in chosen.values()])

    @api.depends('semester_ids')
    def _compute_period_sequence(self):
        for line in self:
            sequences = set(line.semester_ids.mapped('sequence'))
            line.period_sequence = sequences.pop() if len(sequences) == 1 else 0

    @api.onchange('course_ids')
    def _onchange_course_ids(self):
        """Fill the context a fee line needs from the selected courses."""
        if not self.course_ids:
            return
        self.department_ids = self.course_ids.mapped('department_id')
        structure = self.structure_id
        if not structure and self.env.context.get('default_structure_id'):
            structure = self.env['umti.fee.structure'].browse(
                self.env.context['default_structure_id'])
            self.structure_id = structure
        if structure:
            self.company_id = structure.company_id
            self.currency_id = structure.company_id.currency_id
            if not self.academic_year_ids:
                self.academic_year_ids = structure.academic_year_ids
        if not self.academic_year_ids:
            year = self.env['umti.academic.year'].search([
                ('status', '=', 'running'), ('active', '=', True),
            ], order='start_date desc', limit=1)
            if year:
                self.academic_year_ids = year
        self.active = True

    @api.onchange('semester_ids')
    def _onchange_semester_ids(self):
        if self.semester_ids:
            self.academic_year_ids = self.semester_ids.mapped(
                'academic_year_id')
            sequences = set(self.semester_ids.mapped('sequence'))
            self.period_sequence = (
                sequences.pop() if len(sequences) == 1 else 0)

    @api.constrains('structure_id', 'votehead', 'course_ids',
                    'academic_year_ids', 'semester_ids', 'department_ids',
                    'period_sequence')
    def _check_duplicate_votehead(self):
        for line in self:
            others = self.search([
                ('id', '!=', line.id),
                ('structure_id', '=', line.structure_id.id),
                ('votehead', '=', line.votehead.id),
                ('period_sequence', '=', line.period_sequence),
            ])
            for other in others:
                if (set(line.course_ids.ids) == set(other.course_ids.ids)
                        and set(line.academic_year_ids.ids) == set(
                            other.academic_year_ids.ids)
                        and set(line.semester_ids.ids) == set(
                            other.semester_ids.ids)
                        and set(line.department_ids.ids) == set(
                            other.department_ids.ids)):
                    raise ValidationError(_(
                        "Votehead \"%(votehead)s\" already exists with the "
                        "same courses, years, semesters and departments.",
                        votehead=line.votehead.name))

    @api.constrains('semester_ids', 'course_ids', 'academic_year_ids')
    def _check_term_course(self):
        for line in self:
            for term in line.semester_ids:
                if (term.course_id and line.course_ids
                        and term.course_id not in line.course_ids):
                    raise ValidationError(_(
                        "Term %(term)s belongs to %(term_course)s, which is "
                        "not in the selected courses.",
                        term=term.name,
                        term_course=term.course_id.name))
                if (line.academic_year_ids
                        and term.academic_year_id not in line.academic_year_ids):
                    raise ValidationError(_(
                        "Term %(term)s does not belong to the selected "
                        "academic years.", term=term.name))
