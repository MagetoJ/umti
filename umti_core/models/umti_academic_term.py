# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UmtiAcademicTerm(models.Model):
    _name = 'umti.academic.term'
    _description = 'Semester'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'
    _order = 'academic_year_id desc, course_id, sequence'

    name = fields.Char('Name', required=True, tracking=True)
    term_start_date = fields.Date('Start Date', required=True, tracking=True)
    term_end_date = fields.Date('End Date', required=True, tracking=True)
    status = fields.Selection([('draft', 'Draft'),('in_progress', 'In Progress'),('ended', 'Ended')], default='draft', string="Status", tracking=True)
    active= fields.Boolean(default=True, tracking=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True, tracking=True)
    course_id = fields.Many2one(
        'umti.course', string='Course', index=True, ondelete='restrict',
        tracking=True,
        help="Course this term belongs to. Leave empty for a shared or "
             "legacy term that applies to every course.")
    pattern_id = fields.Many2one(
        'umti.term.pattern', string='Term Pattern', ondelete='set null',
        tracking=True,
        help="Pattern snapshot the term was generated from.")
    sequence = fields.Integer(default=10)
    parent_term = fields.Many2one(
        'umti.academic.term', string='Parent Term')
    is_subterm = fields.Boolean(
        compute='_compute_is_subterm', store=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.user.company_id)

    @api.depends('parent_term')
    def _compute_is_subterm(self):
        for term in self:
            term.is_subterm = bool(term.parent_term)

    def action_activate_academic_term(self):
        """Start the term. Only one top-level term per course/intake runs."""
        for term in self:
            if term.status == 'ended':
                raise UserError(_(
                    "Semester %(semester)s has ended and cannot be started again.",
                    semester=term.name))
            if not term.parent_term:
                running = self.search([
                    ('id', '!=', term.id),
                    ('academic_year_id', '=', term.academic_year_id.id),
                    ('course_id', '=', term.course_id.id),
                    ('parent_term', '=', False),
                    ('status', '=', 'in_progress'),
                ], limit=1)
                if running:
                    raise UserError(_(
                        "Semester %(running)s is still in progress. End it "
                        "before starting %(semester)s.",
                        running=running.name, semester=term.name))
            term.write({'status': 'in_progress'})

    def action_end_academic_term(self):
        self.filtered(
            lambda t: t.status == 'in_progress').write({'status': 'ended'})

    #automations and constraints later on
