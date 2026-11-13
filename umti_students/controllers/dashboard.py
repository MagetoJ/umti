from odoo import http
from odoo.http import request


class StudentDashboardController(http.Controller):

    @http.route('/umti/dashboard/student_data', type='json', auth='user')
    def get_student_dashboard_data(self):
        env = request.env

        # 1. KPI Counts
        total_students = env['school.student'].search_count([])
        active_students = env['school.student'].search_count([('state', '=', 'enrolled')])
        graduated_students = env['school.student'].search_count([('state', '=', 'completed')])
        
        # Applications
        total_apps = env['umti.admission.application'].search_count([])
        pending_apps = env['umti.admission.application'].search_count([('state', 'in', ['draft', 'under_review'])])

        # Financials
        fee_records = env['umti.fee.record'].search_read([], ['amount_due', 'amount_paid', 'balance'])
        total_invoiced = sum(f['amount_due'] for f in fee_records)
        total_collected = sum(f['amount_paid'] for f in fee_records)
        total_outstanding = sum(f['balance'] for f in fee_records)

        # 2. Enrollment by Department
        dept_data = env['school.student'].read_group(
            domain=[('department_id', '!=', False)],
            fields=['department_id'],
            groupby=['department_id']
        )
        students_by_dept = [
            {
                'department_name': item['department_id'][1],
                'count': item['department_id_count']
            }
            for item in dept_data
        ]

        # 3. Fee Payment Status Breakdown
        fee_status_data = env['umti.fee.record'].read_group(
            domain=[],
            fields=['state'],
            groupby=['state']
        )
        fee_status_breakdown = [
            {
                'status': item['state'],
                'count': item['state_count']
            }
            for item in fee_status_data
        ]

        return {
            'kpis': {
                'total_students': total_students,
                'active_students': active_students,
                'graduated_students': graduated_students,
                'total_apps': total_apps,
                'pending_apps': pending_apps,
                'total_invoiced': total_invoiced,
                'total_collected': total_collected,
                'total_outstanding': total_outstanding,
            },
            'students_by_dept': students_by_dept,
            'fee_status_breakdown': fee_status_breakdown,
        }