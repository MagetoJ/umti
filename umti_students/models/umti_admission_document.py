# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolAdmissionDocument(models.Model):
    """One document requested by a course, tracked on one application.

    The requirements themselves live on ``umti.course.required.documents``
    (owned by the course); this model only records what the applicant did
    about each of them. Adding a requirement to a course therefore adds a row
    here — no new fields, no code change.
    """

    _name = 'school.admission.document'
    _description = 'Application Document'
    _order = 'requirement_id, id'
    _rec_name = 'name'

    application_id = fields.Many2one(
        'school.admission.application', string='Application', required=True,
        ondelete='cascade', index=True)
    requirement_id = fields.Many2one(
        'umti.course.required.documents', string='Document', required=True,
        ondelete='restrict', index=True)
    name = fields.Char(related='requirement_id.name', store=True)
    code = fields.Char(related='requirement_id.code', store=True)
    waivable = fields.Boolean(related='requirement_id.waivable')
    description = fields.Text(related='requirement_id.description')
    company_id = fields.Many2one(
        related='application_id.company_id', store=True, index=True)

    attachment = fields.Binary(string='File', attachment=True)
    filename = fields.Char()

    verified = fields.Boolean(string='Verified', copy=False)
    waiver_requested = fields.Boolean(string='Waiver Requested', copy=False)
    waiver_reason = fields.Text(string='Waiver Reason')
    waived = fields.Boolean(string='Waived', copy=False)

    status = fields.Selection([
        ('missing', 'Missing'),
        ('uploaded', 'Uploaded'),
        ('verified', 'Verified'),
        ('waived', 'Waived'),
    ], compute='_compute_status', store=True, string='Status')

    _sql_constraints = [
        ('application_requirement_uniq',
         'unique(application_id, requirement_id)',
         'This document is already listed for the application.'),
    ]

    @api.depends('attachment', 'verified', 'waived')
    def _compute_status(self):
        for record in self:
            if record.waived:
                record.status = 'waived'
            elif record.verified:
                record.status = 'verified'
            elif record.attachment:
                record.status = 'uploaded'
            else:
                record.status = 'missing'

    @api.constrains('waived')
    def _check_waivable(self):
        for record in self:
            if record.waived and not record.waivable:
                raise ValidationError(_(
                    '%(document)s cannot be waived for this course.',
                    document=record.name))

    def action_verify(self):
        self.write({'verified': True})

    def action_waive(self):
        """Waive the document, refusing when the requirement is not waivable."""
        not_waivable = self.filtered(lambda record: not record.waivable)
        if not_waivable:
            raise ValidationError(_(
                'These documents cannot be waived: %s',
                ', '.join(not_waivable.mapped('name'))))
        self.write({'waived': True})

    def action_reset(self):
        self.write({'verified': False, 'waived': False})
