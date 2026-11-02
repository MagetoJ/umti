# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class UmtiAcademicTerm(models.Model):
    _name = 'umti.academic.term'
    _description = 'Semester'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Name', required=True, tracking=True)
    term_start_date = fields.Date('Start Date', required=True, tracking=True)
    term_end_date = fields.Date('End Date', required=True, tracking=True)
    status = fields.Selection([('draft', 'Draft'),('in_progress', 'In Progress'),('ended', 'Ended')], default='draft', string="Status", tracking=True)
    active= fields.Boolean(default=True, tracking=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True, tracking=True)
    parent_term = fields.Many2one(
        'umti.academic.term', string='Parent Term')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.user.company_id)

    def action_activate_academic_term(self):
        """Start the term. Only one top-level term per academic year runs."""
        for term in self:
            if term.status == 'ended':
                raise UserError(_(
                    "Semester %(semester)s has ended and cannot be started again.",
                    semester=term.name))
            if not term.parent_term:
                running = term.academic_year_id.academic_term_ids.filtered(
                    lambda t: t != term and not t.parent_term
                    and t.status == 'in_progress')
                if running:
                    raise UserError(_(
                        "Semester %(running)s is still in progress. End it "
                        "before starting %(semester)s.",
                        running=running[0].name, semester=term.name))
            term.write({'status': 'in_progress'})

    def action_end_academic_term(self):
        self.filtered(
            lambda t: t.status == 'in_progress').write({'status': 'ended'})

    #automations and constraints later on
            
