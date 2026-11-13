# -*- coding: utf-8 -*-
from odoo import api,fields,models,_
from odoo.exceptions import UserError
from odoo.tools import html_escape as escape

UNIT_LEVEL_TO_YEAR = {
    'yr_one': 1,
    'yr_two': 2,
    'yr_three': 3,
    'yr_four': 4,
    'other': 1,
}

UNIT_SEMESTER_TO_PERIOD = {
    'sem_1': 10,
    'sem_2': 20,
    'sem_3': 30,
    'sem_4': 40,
    'other': 10,
}


class UmtiCourse(models.Model):
    _name = 'umti.course'
    _description = 'Umti Course'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string="Name", required = True, tracking=True)
    code = fields.Char(string="Code", required = True, copy=False, tracking=True)
    department_id = fields.Many2one("umti.department", string="Department", required=True, tracking=True)
    course_level_id = fields.Many2one("umti.course.level", string="Course Level", required=True, tracking=True)
    term_pattern_id = fields.Many2one(
        'umti.term.pattern', string='Term Pattern', tracking=True,
        domain="[('active', '=', True)]",
        help="Leave empty to follow the pattern set on the course level.")
    effective_term_pattern_id = fields.Many2one(
        'umti.term.pattern', string='Effective Term Pattern',
        compute='_compute_effective_term_pattern_id')
    minimum_credits = fields.Integer(string="Minimum Credits", required=True, tracking=True, help="Minimum credits required to graduate from this course")
    period_type = fields.Selection([('months', 'Months'), ('years', 'Years')], default="years", required=True, tracking=True)
    period = fields.Integer('Period', default=0, tracking=True)
    qualifying_requirement_ids = fields.Many2many( comodel_name='umti.course.qualifying.requirement', relation='umti_course_qualifying_rel', 
        column1='course_id', column2='requirement_id', string="Qualifying Requirements")
    
    general_requirement_ids = fields.Many2many( comodel_name='umti.course.general.requirement',relation='umti_course_general_rel', column1='course_id', 
        column2='requirement_id',string="General Requirements")
    document_ids = fields.Many2many( comodel_name='umti.course.required.documents',relation='umti_course_document_rel', column1='course_id', 
        column2='document_id',string="Required Documents")
    requirements_warning_dismissed = fields.Boolean(copy=False)
    show_setup_warning = fields.Boolean(
        compute='_compute_setup_warning')
    setup_warning_message = fields.Char(
        compute='_compute_setup_warning')
    term_review_dismissed = fields.Boolean(copy=False)
    generated_term_ids = fields.Many2many(
        'umti.academic.term', string='Generated Semesters',
        compute='_compute_generated_terms')
    generated_term_summary = fields.Html(
        compute='_compute_generated_terms')
    show_generated_terms_warning = fields.Boolean(
        compute='_compute_generated_terms')
    unit_ids = fields.Many2many(comodel_name='umti.course.units', relation='umti_course_unit_rel', column1='course_id', column2='unit_id', string="Units")
    unit_line_ids = fields.One2many(
        'umti.course.unit.line', 'course_id', string='Unit Plan', copy=True)
    course_capacity = fields.Integer(string="Course Capacity", tracking=True, default=0, copy=False)
    course_quorum = fields.Integer(string="Course Quorum", tracking=True, default=1, copy=False)
    quorum_progress = fields.Integer(string="Course Quorum", compute="_compute_counts",)
    status = fields.Selection([('draft', 'Draft'),('active', 'Active'),('discontinued', 'Discontinued')], default='draft', string="Status", tracking=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)
    unit_credit_totals = fields.Integer(string="Unit Credits", compute="_compute_counts",)
    totals_progress = fields.Integer(string="Unit Credits", compute="_compute_counts",)
    active = fields.Boolean(default=True, tracking=True)


    @api.model_create_multi
    def create(self, vals_list):
        courses = super().create(vals_list)
        courses._sync_unit_plan_from_units()
        courses._seed_fee_structure_lines()
        return courses

    def _seed_fee_structure_lines(self):
        """Put a new course on the current proposed fee structure.

        Lines are created with zero amounts for every active votehead, so the
        structure is never missing a votehead for a course; finance fills in
        the amounts.
        """
        Structure = self.env['umti.fee.structure']
        for course in self:
            structure = Structure.search([
                ('company_id', '=', course.company_id.id),
                ('active', '=', True),
                ('status', 'in', ('proposed', 'active')),
            ], order='status desc, active_from desc, id desc', limit=1)
            if structure:
                structure._ensure_lines_for_course(course)

    def write(self, vals):
        requirement_fields = {
            'document_ids', 'qualifying_requirement_ids',
            'general_requirement_ids',
        }
        if requirement_fields & set(vals):
            # Requirements changed: show the banner again so the user sees
            # whatever else is still missing.
            vals = dict(vals, requirements_warning_dismissed=False)
        res = super().write(vals)
        if 'unit_ids' in vals:
            self._sync_unit_plan_from_units()
        return res

    def _sync_unit_plan_from_units(self):
        """Keep the Unit Plan in step with the course's Units tab.

        Units added to the course get a plan line using the defaults stored
        on the unit; placement is then owned by the course, so changing the
        unit for one course never moves it in another. Lines for units
        removed from the course are dropped so they cannot enrol students
        by accident.
        """
        Line = self.env['umti.course.unit.line']
        for course in self:
            course.unit_line_ids.filtered(
                lambda line: line.unit_id not in course.unit_ids).unlink()
            placed = course.unit_line_ids.mapped('unit_id')
            pattern = course._get_term_pattern()
            main_lines = pattern._main_lines() if pattern else False
            sequences = main_lines.mapped('sequence') if main_lines else []
            semester_index = {
                'sem_1': 0, 'sem_2': 1, 'sem_3': 2, 'sem_4': 3,
                'other': 0,
            }
            vals_list = []
            for unit in course.unit_ids - placed:
                index = semester_index.get(unit.unit_semester, 0)
                if sequences:
                    period = sequences[
                        min(index, len(sequences) - 1)]
                else:
                    period = UNIT_SEMESTER_TO_PERIOD.get(
                        unit.unit_semester, 10)
                vals_list.append({
                    'course_id': course.id,
                    'unit_id': unit.id,
                    'course_year': UNIT_LEVEL_TO_YEAR.get(
                        unit.unit_level, 1),
                    'period_sequence': period,
                    'phase': ('attachment'
                              if unit.unit_type == 'attachment'
                              else 'taught'),
                })
            if vals_list:
                Line.create(vals_list)

    def action_fill_unit_plan_from_units(self):
        self._sync_unit_plan_from_units()

    @api.depends('unit_ids', 'term_pattern_id', 'course_level_id',
                 'course_level_id.term_pattern_id', 'term_review_dismissed')
    def _compute_generated_terms(self):
        Term = self.env['umti.academic.term']
        year = self.env['umti.academic.year'].search([
            ('status', '=', 'running'), ('active', '=', True),
        ], order='start_date desc', limit=1)
        for course in self:
            pattern = course.effective_term_pattern_id
            lines = pattern._main_lines() if pattern else False
            if not course.unit_ids or not lines or len(lines) <= 1:
                course.generated_term_ids = False
                course.generated_term_summary = False
                course.show_generated_terms_warning = False
                continue
            domain = [
                ('course_id', '=', course.id),
                ('parent_term', '=', False),
                ('active', '=', True),
            ]
            if year:
                domain.append(('academic_year_id', '=', year.id))
            terms = Term.search(domain, order='term_start_date')
            course.generated_term_ids = terms
            rows = []
            for term in terms:
                start = (term.term_start_date.strftime('%d %b %Y')
                         if term.term_start_date else '')
                end = (term.term_end_date.strftime('%d %b %Y')
                       if term.term_end_date else '')
                rows.append(
                    "<div><strong>%s</strong> "
                    "<span class='text-muted'>%s - %s</span></div>"
                    % (escape(term.name), start, end))
            course.generated_term_summary = ''.join(rows)
            course.show_generated_terms_warning = bool(
                terms) and not course.term_review_dismissed

    @api.depends('document_ids', 'qualifying_requirement_ids',
                 'general_requirement_ids', 'requirements_warning_dismissed')
    def _compute_setup_warning(self):
        for course in self:
            missing = []
            if not course.document_ids:
                missing.append(_('required documents'))
            if not course.qualifying_requirement_ids:
                missing.append(_('qualifying requirements'))
            if not course.general_requirement_ids:
                missing.append(_('general requirements'))
            if missing:
                if len(missing) == 1:
                    joined = missing[0]
                else:
                    joined = _('%s or %s', ', '.join(missing[:-1]),
                               missing[-1])
                course.setup_warning_message = _(
                    "This course setup might be incomplete. There are no %s.",
                    joined)
            else:
                course.setup_warning_message = False
            course.show_setup_warning = bool(
                missing) and not course.requirements_warning_dismissed

    def action_dismiss_setup_warning(self):
        self.write({'requirements_warning_dismissed': True})

    def action_review_generated_terms(self):
        self.write({'term_review_dismissed': True})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Semesters'),
            'res_model': 'umti.academic.term',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.generated_term_ids.ids)],
            'context': {'default_course_id': self.id},
        }

    def _compute_counts(self):
        for record in self:
            if record.unit_ids:
                record.unit_credit_totals = sum(unit.credit_contribution for unit in record.unit_ids)
                if record.minimum_credits:
                    record.totals_progress = (record.unit_credit_totals / record.minimum_credits) * 100
                else:
                    record.totals_progress = 0
            else:
                record.unit_credit_totals = 0
                record.totals_progress = 0

            # Compute Quorum Progress
            if record.course_capacity and record.course_quorum:
                record.quorum_progress = (record.course_quorum / record.course_capacity) * 100
            else:
                record.quorum_progress = 0

    @api.depends('term_pattern_id', 'course_level_id',
                 'course_level_id.term_pattern_id')
    def _compute_effective_term_pattern_id(self):
        default = self.env['umti.term.pattern']._default_pattern()
        for course in self:
            course.effective_term_pattern_id = (
                course.term_pattern_id
                or course.course_level_id.term_pattern_id
                or default)

    def _get_term_pattern(self):
        self.ensure_one()
        return self.effective_term_pattern_id


    #automatically compute period if period_type is changed
    @api.onchange('period_type')
    def _onchange_period_type(self):
        """
        This method is called when the period_type field is changed.
        It automatically computes the period field based on the period_type field.
        """

        if not self.period:
            return

        if self.period_type == 'years':
            self.period = max(1, int(self.period / 12))
        elif self.period_type == 'months':
            self.period = self.period * 12
    
    def activate_course(self):
        for course in self:
            if not course.minimum_credits:
                raise UserError(_('Minimum Credits is not set.'))
            if not course.period:
                raise UserError(_('Course Period is not set.'))
            if not course.course_capacity:
                raise UserError(_('Mandated Capacity is not set.'))
            course.write({'active': True})
            course._ensure_terms_for_running_year()
            if not any(course.unit_ids):
                raise UserError(_('Units are not set.'))            
            if course.unit_credit_totals < course.minimum_credits:
                raise UserError(_('Unit Credits set so far is less than Minimum Credits.'))            
            # Requirements are advisory: the course form shows dismissible
            # banners instead of blocking activation.
        self.write({'status': 'active'})

    #later on, prevent discontinuing a course if it has student
    def _ensure_terms_for_running_year(self):
        """Give a course activated mid-year its share of the running terms."""
        year = self.env['umti.academic.year'].search([
            ('status', '=', 'running'),
            ('active', '=', True),
        ], order='start_date desc', limit=1)
        if not year:
            return
        for course in self:
            pattern = course._get_term_pattern()
            if pattern and pattern.anchor == 'academic_year':
                end = (None if pattern.scope == 'whole_course'
                       else year.end_date)
                year.generate_course_terms(
                    course, year.start_date, end, year=year)

    def discontinue_course(self):
        pass