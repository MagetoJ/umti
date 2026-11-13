from odoo import fields, models


class UmtiCaseMixin(models.AbstractModel):
    _name = 'umti.case.mixin'
    _description = 'Student Case Mixin'

    assigned_to = fields.Many2one(
        'res.users', string='Assigned To',
        default=lambda self: self.env.user)
    opened_date = fields.Date(default=fields.Date.context_today)
    closed_date = fields.Date(readonly=True)
    resolution = fields.Text()

