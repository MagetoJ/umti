from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    umti_votehead_id = fields.Many2one(
        'umti.structure.votehead', string='Fee Votehead',
        readonly=True, copy=False)
    umti_refundable = fields.Boolean(
        string='Refundable on Graduation', readonly=True, copy=False,
        help="Set on intake invoice lines whose votehead is refundable, so "
             "the graduation credit note can be traced back to them.")
