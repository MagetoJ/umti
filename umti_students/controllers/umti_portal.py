# -*- coding: utf-8 -*-
import base64

from odoo import http
from odoo.http import request


class UmtiStudentPortfolioPortal(http.Controller):

    @http.route('/my/portfolio', type='http', auth='user', website=True)
    def my_portfolio(self, **kw):
        # Only ever look up the record linked to the logged-in user.
        student = request.env['school.student'].sudo().search(
            [('user_id', '=', request.env.user.id)], limit=1)
        return request.render('umti_students.portal_portfolio', {
            'student': student,
            'fees': student.student_fee_record_ids.sorted('date', reverse=True),
            'exams': student.exam_record_ids.sorted('exam_date', reverse=True),
            'page_name': 'portfolio',
        })

    @http.route('/my/portfolio/receipt/<int:record_id>', type='http', auth='user', website=True)
    def download_receipt(self, record_id, **kw):
        rec = request.env['umti.fee.record'].sudo().browse(record_id)
        if (not rec.exists() or rec.student_id.user_id != request.env.user
                or not rec.receipt_file):
            return request.not_found()
        content = base64.b64decode(rec.receipt_file)
        name = rec.receipt_filename or ('receipt_%s' % (rec.receipt_no or rec.id))
        return request.make_response(content, headers=[
            ('Content-Type', 'application/octet-stream'),
            ('Content-Disposition', http.content_disposition(name)),
        ])
