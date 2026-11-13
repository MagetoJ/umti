# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolAdmissionRequirement(models.Model):
    """One requirement (qualifying or general) tracked on one application.

    Exactly the same idea as ``school.admission.document``: the requirements
    live on the course, this model only records whether the applicant met
    them, asked for a waiver, or was waived.
    """
    _name = 'school.admission.requirement'
    _description = 'Application Requirement'
    _order = 'kind, name, id'
    _rec_name = 'name'

    application_id = fields.Many2one(
        'school.admission.application', string='Application', required=True,
        ondelete='cascade', index=True)
    kind = fields.Selection([
        ('qualifying', 'Qualifying'),
        ('general', 'General'),
    ], required=True, index=True)
    qualifying_id = fields.Many2one(
        'umti.course.qualifying.requirement', string='Requirement',
        ondelete='restrict', index=True)
    general_id = fields.Many2one(
        'umti.course.general.requirement', string='Requirement',
        ondelete='restrict', index=True)
    company_id = fields.Many2one(
        related='application_id.company_id', store=True, index=True)

    # Snapshot of whichever requirement this line points at.
    name = fields.Char(compute='_compute_source', store=True)
    description = fields.Text(compute='_compute_source', store=True)
    required_mark = fields.Char(compute='_compute_source', store=True)
    waivable = fields.Boolean(compute='_compute_source', store=True)

    met = fields.Boolean(string='Met', copy=False)
    waiver_requested = fields.Boolean(string='Waiver Requested', copy=False)
    waiver_reason = fields.Text(string='Waiver Reason')
    waived = fields.Boolean(string='Waived', copy=False)

    status = fields.Selection([
        ('pending', 'Pending'),
        ('met', 'Met'),
        ('waived', 'Waived'),
    ], compute='_compute_status', store=True, string='Status')

    _sql_constraints = [
        ('application_qualifying_uniq',
         'unique(application_id, qualifying_id)',
         'This requirement is already listed for the application.'),
        ('application_general_uniq',
         'unique(application_id, general_id)',
         'This requirement is already listed for the application.'),
    ]

    @api.depends('kind', 'qualifying_id', 'general_id')
    def _compute_source(self):
        for record in self:
            source = record.qualifying_id or record.general_id
            record.name = source.name or ''
            record.description = source.description or ''
            record.required_mark = record.qualifying_id.required_mark or ''
            record.waivable = bool(source.waivable)

    @api.depends('met', 'waived')
    def _compute_status(self):
        for record in self:
            if record.waived:
                record.status = 'waived'
            elif record.met:
                record.status = 'met'
            else:
                record.status = 'pending'

    @api.constrains('kind', 'qualifying_id', 'general_id')
    def _check_source(self):
        for record in self:
            if record.kind == 'qualifying' and (not record.qualifying_id
                                                or record.general_id):
                raise ValidationError(_(
                    'A qualifying requirement line must point at a '
                    'qualifying requirement.'))
            if record.kind == 'general' and (not record.general_id
                                             or record.qualifying_id):
                raise ValidationError(_(
                    'A general requirement line must point at a general '
                    'requirement.'))

    @api.constrains('waived')
    def _check_waivable(self):
        for record in self:
            if record.waived and not record.waivable:
                raise ValidationError(_(
                    '%(requirement)s cannot be waived for this course.',
                    requirement=record.name))

    def action_mark_met(self):
        self.write({'met': True})

    def action_waive(self):
        not_waivable = self.filtered(lambda record: not record.waivable)
        if not_waivable:
            raise ValidationError(_(
                'These requirements cannot be waived: %s',
                ', '.join(not_waivable.mapped('name'))))
        self.write({'waived': True})

    def action_reset(self):
        self.write({'met': False, 'waived': False})
