from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Extract / OCR fields
    extract_error_message = fields.Text(string="Extract Error Message", readonly=True)
    extract_document_uuid = fields.Char(string="Extract Document UUID", readonly=True)
    extract_attachment_id = fields.Many2one('ir.attachment', string="Extract Attachment", readonly=True)
    extract_word_ids = fields.Many2many('ir.attachment', string="Extract Words", readonly=True)
    extract_state = fields.Selection(
        [
            ('no_extract_requested', 'No extract requested'),
            ('not_enough_credit', 'Not enough credit'),
            ('error_status', 'An error occurred'),
            ('waiting_extraction', 'Waiting extraction'),
            ('extract_not_ready', 'Extract not ready'),
            ('waiting_validation', 'Waiting validation'),
            ('done', 'Completed'),
        ],
        string="Extract State",
        default='no_extract_requested',
        readonly=True,
    )
    extract_status_code = fields.Integer(string="Extract Status Code", readonly=True)
    extract_can_show_send_button = fields.Boolean(string="Can Show Send Button", readonly=True)