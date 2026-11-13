from odoo import http
from odoo.http import request


class LibraryDashboardController(http.Controller):

    @http.route('/umti/dashboard/library_data', type='json', auth='user')
    def get_library_dashboard_data(self):
        env = request.env

        total_books = env['umti.library.books'].search_count([])
        total_copies_data = env['umti.library.books'].search_read([], ['total_copies', 'available_copies'])
        sum_total_copies = sum(b['total_copies'] for b in total_copies_data)
        sum_available_copies = sum(b['available_copies'] for b in total_copies_data)

        active_loans = env['umti.library.lending'].search_count([('state', '=', 'issued')])
        overdue_loans = env['umti.library.lending'].search_count([('state', '=', 'overdue')])

        # Overdue Loans Table Top 5
        overdue_list = env['umti.library.lending'].search_read(
            domain=[('state', '=', 'overdue')],
            fields=['student_id', 'book_id', 'due_date', 'fine_amount'],
            limit=5
        )
        formatted_overdue = [
            {
                'student': rec['student_id'][1] if rec['student_id'] else 'N/A',
                'book': rec['book_id'][1] if rec['book_id'] else 'N/A',
                'due_date': str(rec['due_date']),
                'fine': rec['fine_amount']
            }
            for rec in overdue_list
        ]

        return {
            'kpis': {
                'total_titles': total_books,
                'total_copies': sum_total_copies,
                'available_copies': sum_available_copies,
                'active_loans': active_loans,
                'overdue_loans': overdue_loans,
            },
            'overdue_list': formatted_overdue,
        }