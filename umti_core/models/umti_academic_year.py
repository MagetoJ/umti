# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UmtiAcademicYear(models.Model):
    _name = 'umti.academic.year'
    _description = 'Umti Academic Year'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Name', readonly=True, compute='_compute_name',store=True, tracking=True)
    start_date = fields.Date('Start Date', required=True, tracking=True)
    end_date = fields.Date('End Date', required=True, tracking=True)
    status = fields.Selection([('draft', 'Draft'),('running', 'Running'),('ended', 'Ended')], default='draft', string="Status", tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    academic_term_ids = fields.One2many('umti.academic.term', 'academic_year_id', string="Semesters")
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.user.company_id)

     #constraints
    @api.constrains('start_date', 'end_date')
    def _check_overlapping_academic_year(self):
        for record in self:
            if record.start_date and record.end_date:
                # Always ensure chronological alignment first
                if record.start_date > record.end_date:
                    raise ValidationError(_("The start date must be before the end date."))

                # Look for ANY overlapping ranges in the database
                overlapping_year = self.search([
                    ('id', '!=', record.id), # Exclude current record
                    ('start_date', '<=', record.end_date),
                    ('end_date', '>=', record.start_date),
                    ('active', '=', True),
                ], limit=1)

                if overlapping_year:
                    raise ValidationError(_(
                        "This timeframe overlaps with an existing academic year: %s (%s to %s)."
                    ) % (overlapping_year.name, overlapping_year.start_date, overlapping_year.end_date))


    #standardize academic year names
    @api.depends('start_date', 'end_date')
    def _compute_name(self):
        for record in self:
            if record.start_date and record.end_date:
                start_year = record.start_date.strftime('%Y')
                end_year = record.end_date.strftime('%Y')
                
                if start_year != end_year:
                    record.name = f"{start_year} - {end_year}"
                else:
                    record.name = start_year
            else:
                record.name = "New Academic Year"


    @api.model
    def _get_term_structure(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'umti_core.school_term_structure', 'two_sem')

    # ------------------------------------------------------------------
    # Term generation from course patterns
    # ------------------------------------------------------------------
    @api.model
    def _year_for_date(self, date):
        """The academic year that owns a date, or the next one if none does."""
        year = self.search([
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('active', '=', True),
        ], order='start_date desc', limit=1)
        if year:
            return year
        return self.search([
            ('start_date', '>', date),
            ('active', '=', True),
        ], order='start_date', limit=1)

    @api.model
    def _course_duration(self, course):
        """Course length in months, or 0 when it is not configured."""
        if not course.period:
            return 0
        return course.period * 12 if course.period_type == 'years' else course.period

    @api.model
    def _course_end(self, course, start):
        months = self._course_duration(course)
        if not months:
            return None
        return start + relativedelta(months=months) - timedelta(days=1)

    def _course_span(self, course, pattern):
        """Span covered by this year's generation for a course."""
        self.ensure_one()
        start = self.start_date
        if pattern.scope == 'whole_course':
            return start, self._course_end(course, start) or self.end_date
        return start, self.end_date

    @api.model
    def _split_span(self, lines, start, end):
        """Split ``start..end`` across pattern lines.

        Lines with ``duration_value`` take that length; lines with 0 share
        whatever is left equally. The last line always ends at ``end``.
        """
        lines = lines.sorted('sequence')
        if not lines or not start or not end:
            return {}
        if end < start:
            end = start
        result = {}
        cursor = start
        auto_left = len(lines.filtered(lambda line: not line.duration_value))
        for index, line in enumerate(lines):
            is_last = index == len(lines) - 1
            if is_last:
                line_end = end
            elif line.duration_value:
                line_end = cursor + self._relativedelta(
                    line.duration_value, line.duration_unit) - timedelta(days=1)
                if line_end > end:
                    line_end = end
            else:
                days_left = (end - cursor).days + 1
                share = days_left // max(auto_left, 1)
                line_end = cursor + timedelta(days=max(share - 1, 0))
                auto_left = max(auto_left - 1, 1)
            result[line.id] = (cursor, line_end)
            cursor = line_end + timedelta(days=1)
            if cursor > end:
                cursor = end
        return result

    @api.model
    def _relativedelta(self, value, unit):
        if unit == 'days':
            return relativedelta(days=value)
        if unit == 'weeks':
            return relativedelta(weeks=value)
        return relativedelta(months=value)

    @api.model
    def _term_name(self, course, line_name, start):
        """Human-readable term name: course, period and start month."""
        label = course.name or course.code or ''
        name = f"{label} - {line_name}" if label else line_name
        if start:
            name = f"{name} ({start.strftime('%b %Y')})"
        return name

    @api.model
    def _create_terms_from_pattern(self, year, course, pattern, start, end):
        Term = self.env['umti.academic.term']
        main_lines = pattern._main_lines()
        spans = self._split_span(main_lines, start, end)
        created = Term
        by_sequence = {}
        for line in main_lines:
            line_start, line_end = spans[line.id]
            term = Term.create({
                'name': self._term_name(course, line.name, line_start),
                'term_start_date': line_start,
                'term_end_date': line_end,
                'academic_year_id': year.id,
                'course_id': course.id,
                'pattern_id': pattern.id,
                'sequence': line.sequence,
                'status': 'draft',
                'company_id': (course.company_id or year.company_id).id,
            })
            by_sequence[line.sequence] = term
            created |= term
        for line in main_lines:
            parent = by_sequence[line.sequence]
            children = pattern._child_lines(line.sequence)
            child_spans = self._split_span(
                children, parent.term_start_date, parent.term_end_date)
            for child in children:
                child_start, child_end = child_spans[child.id]
                term = Term.create({
                    'name': self._term_name(course, child.name, child_start),
                    'term_start_date': child_start,
                    'term_end_date': child_end,
                    'academic_year_id': year.id,
                    'course_id': course.id,
                    'pattern_id': pattern.id,
                    'sequence': child.sequence,
                    'parent_term': parent.id,
                    'status': 'draft',
                    'company_id': (course.company_id or year.company_id).id,
                })
                created |= term
        return created

    @api.model
    def _normalize_terms(self, terms):
        """The first main term of one generated set runs; the rest wait."""
        main_terms = terms.filtered(lambda term: not term.parent_term).sorted(
            'term_start_date')
        if not main_terms:
            return
        running = main_terms[0]
        for term in terms:
            if term.status == 'ended':
                continue
            should_run = term == running or term.parent_term == running
            wanted = 'in_progress' if should_run else 'draft'
            if term.status != wanted:
                term.write({'status': wanted})

    @api.model
    def generate_course_terms(self, course, start, end=None, year=None):
        """Create the term set of ``course`` for an explicit span.

        Used both by the yearly generation (``anchor='academic_year'``) and
        by intake-anchored courses, whose dates come from the intake.
        """
        pattern = course._get_term_pattern()
        if not pattern or not pattern.line_ids:
            return self.env['umti.academic.term']
        start = fields.Date.to_date(start)
        end = fields.Date.to_date(end) if end else self._course_end(
            course, start)
        if not start or not end:
            return self.env['umti.academic.term']
        year = year or self._year_for_date(start)
        if not year:
            raise ValidationError(_(
                "No academic year contains %(date)s. Create the academic year "
                "before generating terms for %(course)s.",
                date=start, course=course.display_name))
        Term = self.env['umti.academic.term']
        existing = Term.search([
            ('academic_year_id', '=', year.id),
            ('course_id', '=', course.id),
            ('term_start_date', '=', start),
        ])
        if existing:
            return existing
        created = self._create_terms_from_pattern(
            year, course, pattern, start, end)
        self._normalize_terms(created)
        course.write({'term_review_dismissed': False})
        return created

    def _generate_terms(self):
        """Generate course-scoped terms for this academic year.

        Only courses anchored to the academic year are generated here;
        intake-anchored courses are generated when their intake opens.
        """
        for year in self:
            domain = [
                ('active', '=', True),
                ('status', '!=', 'discontinued'),
            ]
            if year.company_id:
                domain.append(
                    ('company_id', 'in', [year.company_id.id, False]))
            courses = self.env['umti.course'].search(domain)
            for course in courses:
                pattern = course._get_term_pattern()
                if not pattern or pattern.anchor != 'academic_year':
                    continue
                start, end = year._course_span(course, pattern)
                if start and end:
                    self.generate_course_terms(
                        course, start, end, year=year)
            year.write({'status': 'running'})

    def activate_academic_year(self):
        self._generate_terms()
        self.write({'status': 'running'})

    def close_academic_year(self):
        self.write({'status': 'ended'})

    def _cron_autoactivate_academic_year(self):
        pass#TODO
