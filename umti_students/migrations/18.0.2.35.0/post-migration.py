from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Move = env['account.move']
    invoices = Move.search([
        ('umti_invoice_kind', '=', 'intake'),
        ('state', '!=', 'cancel'),
    ])
    for invoice in invoices:
        voteheads = invoice.invoice_line_ids.umti_votehead_id
        if not voteheads or not invoice.umti_academic_term_id:
            continue
        if any(votehead.paid_once or votehead.refundable
               for votehead in voteheads):
            continue
        # If a semester invoice was already generated for this term, leave
        # the older intake invoice alone: reclassifying it would double-count
        # the term.
        if Move.search_count([
            ('move_type', '=', 'out_invoice'),
            ('umti_invoice_kind', '=', 'semester'),
            ('umti_student_id', '=', invoice.umti_student_id.id),
            ('umti_academic_term_id', '=', invoice.umti_academic_term_id.id),
            ('state', '!=', 'cancel'),
        ]):
            continue
        invoice.write({'umti_invoice_kind': 'semester'})
