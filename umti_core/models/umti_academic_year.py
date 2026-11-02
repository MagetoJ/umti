# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields, models, api, _
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

    def _compute_is_other_term_structure(self):
        is_other = self._get_term_structure() == 'others'
        for record in self:
            record.is_other_term_structure = is_other

    #TODO: Add a method to activate and deactivate terms automatically
    #TODO: Close an Academic year automatically when all child terms are closed
    def _generate_terms(self):
        # Only years generated right now get their statuses normalised;
        # existing years keep their lifecycle.
        new_years = self.filtered(lambda y: not y.academic_term_ids)
        num = 0
        final = 1
        term_structure = self._get_term_structure()
        academic_terms = self.env['umti.academic.term'].search([])
        if term_structure == 'two_sem':
            for record in self:
                if not record.academic_term_ids:
                    from_d = self.start_date
                    to_d = self.end_date
                    delta = to_d - from_d
                    res = []
                    day = (delta.days + 1) / 2
                    vals = {'name': 'Semester 1',
                            'from_date': from_d,
                            'to_date': (from_d + timedelta(days=day))}
                    res.append(vals)
                    vals = {'name': 'Semester 2',
                            'from_date': (from_d + timedelta(days=day + 1)),
                            'to_date': to_d}
                    res.append(vals)
                    for term in res:
                        academic_terms.create({
                            'name': term['name'],
                            'term_start_date': term['from_date'],
                            'term_end_date': term['to_date'],
                            'academic_year_id': self.id,
                            'status': 'in_progress'
                        })
                    
            self.write({'status': 'running'})

        elif term_structure == 'two_sem_qua':
            for record in self:
                if not record.academic_term_ids:
                    from_d = self.start_date
                    to_d = self.end_date
                    delta = to_d - from_d
                    res = []
                    day = (delta.days + 1) / 2
                    vals = {'name': 'Semester 1',
                            'from_date': from_d,
                            'to_date': (from_d + timedelta(days=day))}
                    res.append(vals)
                    vals = {'name': 'Semester 2',
                            'from_date': (from_d + timedelta(days=day + 1)),
                            'to_date': to_d}
                    res.append(vals)
                    for term in res:
                        academic_terms.create({
                            'name': term['name'],
                            'term_start_date': term['from_date'],
                            'term_end_date': term['to_date'],
                            'academic_year_id': self.id,
                            'status': 'in_progress'
                        })
                        for sub_term in self.academic_term_ids:
                            sub_from_d = sub_term.term_start_date
                            sub_to_d = sub_term.term_end_date
                            delta = sub_to_d - sub_from_d
                            result = []
                            day = (delta.days + 1) / 2
                            vals = {'name': 'Quarter' + ' ' + str(num+1),
                                    'from_date': sub_from_d,
                                    'to_date': (sub_from_d + timedelta(days=day))}
                            result.append(vals)
                            vals = {'name': 'Quarter' + ' ' + str(num+2),
                                    'from_date': (sub_from_d + timedelta(
                                        days=day + 1)),
                                    'to_date': sub_to_d}
                            result.append(vals)
                        num = num + 2

                        for in_terms in result:
                            academic_terms.create({
                                'name': in_terms['name'],
                                'term_start_date': in_terms['from_date'],
                                'term_end_date': in_terms['to_date'],
                                'academic_year_id': self.id,
                                'status': 'in_progress',
                                'parent_term': sub_term.id
                            })
                    
            self.write({'status': 'running'})   
        elif term_structure == 'two_sem_final':
            for record in self:
                if not record.academic_term_ids:
                    from_d = self.start_date
                    to_d = self.end_date
                    delta = to_d - from_d
                    res = []
                    day = (delta.days + 1) / 2
                    vals = {'name': 'Semester 1',
                            'from_date': from_d,
                            'to_date': (from_d + timedelta(days=day))}
                    res.append(vals)
                    vals = {'name': 'Semester 2',
                            'from_date': (from_d + timedelta(days=day + 1)),
                            'to_date': to_d}
                    res.append(vals)

                    for term in res:
                        academic_terms.create({
                            'name': term['name'],
                            'term_start_date': term['from_date'],
                            'term_end_date': term['to_date'],
                            'academic_year_id': self.id,
                            'status': 'in_progress'
                        })

                        for sub_term in self.academic_term_ids:
                            sub_from_d = sub_term.term_start_date
                            sub_to_d = sub_term.term_end_date
                            delta = sub_to_d - sub_from_d
                            result = []

                            day = (delta.days + 1) / 2
                            vals = {'name': 'Quarter' + ' ' + str(num+1),
                                    'from_date': sub_from_d,
                                    'to_date': (sub_from_d + timedelta(days=day))}
                            result.append(vals)
                            vals = {'name': 'Quarter' + ' ' + str(num + 2),
                                    'from_date': (sub_from_d + timedelta(
                                        days=day + 1)),
                                    'to_date': (sub_from_d + timedelta(
                                        days=delta.days - 1))}
                            result.append(vals)
                            vals = {'name': 'Final Exam' + ' ' + str(final),
                                    'from_date': sub_to_d,
                                    'to_date': sub_to_d}
                            result.append(vals)
                        num = num + 2
                        final = final + 1

                        for in_terms in result:
                            academic_terms.create({
                                'name': in_terms['name'],
                                'term_start_date': in_terms['from_date'],
                                'term_end_date': in_terms['to_date'],
                                'academic_year_id': self.id,
                                'parent_term': sub_term.id,
                                'status': 'in_progress'
                            })

                            self.write({'status': 'running'})

        elif term_structure == 'three_sem':
            for record in self:
                if not record.academic_term_ids:
                    from_d = self.start_date
                    to_d = self.end_date
                    delta = to_d - from_d
                    res = []
                    day = (delta.days + 1) / 3
                    to_date1 = (from_d + timedelta(days=day))
                    from_date1 = (from_d + timedelta(days=day + 1))
                    to_date2 = (from_date1 + timedelta(days=day))
                    from_date2 = (from_date1 + timedelta(days=day + 1))

                    vals = {'name': 'Semester 1',
                            'from_date': from_d,
                            'to_date': to_date1}
                    res.append(vals)

                    vals = {'name': 'Semester 2',
                            'from_date': from_date1,
                            'to_date': to_date2}
                    res.append(vals)

                    vals = {'name': 'Semester 3',
                            'from_date': from_date2,
                            'to_date': to_d}
                    res.append(vals)
                    for term in res:
                        academic_terms.create({
                            'name': term['name'],
                            'term_start_date': term['from_date'],
                            'term_end_date': term['to_date'],
                            'status': 'in_progress',
                            'academic_year_id': self.id
                        })
                        self.write({'status': 'running'})

        elif term_structure == 'four_Quarter':
            for record in self:
                if not record.academic_term_ids:
                    from_d = self.start_date
                    to_d = self.end_date
                    delta = to_d - from_d
                    res = []
                    day = (delta.days + 1) / 4

                    to_date1 = (from_d + timedelta(days=day))
                    from_date1 = (from_d + timedelta(days=day + 1))
                    to_date2 = (from_date1 + timedelta(days=day))
                    from_date2 = (from_date1 + timedelta(days=day + 1))
                    to_date3 = (from_date2 + timedelta(days=day))
                    from_date3 = (from_date2 + timedelta(days=day + 1))

                    vals = {'name': 'Semester 1',
                            'from_date': from_d,
                            'to_date': to_date1}
                    res.append(vals)

                    vals = {'name': 'Semester 2',
                            'from_date': from_date1,
                            'to_date': to_date2}
                    res.append(vals)

                    vals = {'name': 'Semester 3',
                            'from_date': from_date2,
                            'to_date': to_date3}
                    res.append(vals)

                    vals = {'name': 'Semester 4',
                            'from_date': from_date3,
                            'to_date': to_d}
                    res.append(vals)

                    for term in res:
                        academic_terms.create({
                            'name': term['name'],
                            'term_start_date': term['from_date'],
                            'term_end_date': term['to_date'],
                            'status': 'in_progress',
                            'academic_year_id': self.id
                        })
                        self.write({'status': 'running'})

        new_years._normalize_term_status()

    def _normalize_term_status(self):
        """Only the first term of a year runs; the others wait as drafts.

        Terms are generated for the whole year at once, so activating them
        all (as the generator used to) would leave several "in progress" and
        defeat any downstream filter on the running term.
        """
        for year in self:
            terms = year.academic_term_ids
            if not terms:
                continue
            main_terms = terms.filtered(
                lambda t: not t.parent_term).sorted('term_start_date')
            if not main_terms:
                continue
            running = main_terms[0]
            for term in terms:
                # Sub-terms follow their parent; everything else is draft.
                should_run = term == running or term.parent_term == running
                wanted = 'in_progress' if should_run else 'draft'
                if term.status != wanted:
                    term.write({'status': wanted})

    def activate_academic_year(self):
        self._generate_terms()
        # The first term runs; _generate_terms already leaves it in progress.
        first_term = self.academic_term_ids.filtered(
            lambda t: not t.parent_term).sorted('term_start_date')[:1]
        if first_term and first_term.status != 'in_progress':
            first_term.action_activate_academic_term()
        self.write({'status': 'running'})

    def close_academic_year(self):
        self.write({'status': 'ended'})

    def _cron_autoactivate_academic_year(self):
        pass#TODO
