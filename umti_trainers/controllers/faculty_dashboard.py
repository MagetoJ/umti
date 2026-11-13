from odoo import http
from odoo.http import request


class FacultyDashboardController(http.Controller):

    @http.route('/umti/dashboard/faculty_data', type='json', auth='user')
    def get_faculty_dashboard_data(self):
        env = request.env

        total_trainers = env['umti.unit.trainer'].search_count([])
        total_allocations = env['umti.trainer.allocation'].search_count([('state', '=', 'approved')])
        
        schemes_total = env['umti.scheme.of.work'].search_count([])
        schemes_approved = env['umti.scheme.of.work'].search_count([('state', '=', 'approved')])
        schemes_pending = env['umti.scheme.of.work'].search_count([('state', '=', 'submitted')])

        workplans_total = env['umti.work.plan'].search_count([])
        workplans_done = env['umti.work.plan'].search_count([('state', '=', 'completed')])

        # Workload per Trainer
        alloc_group = env['umti.trainer.allocation'].read_group(
            domain=[('state', '=', 'approved')],
            fields=['trainer_id'],
            groupby=['trainer_id']
        )
        trainer_workload = [
            {
                'trainer_name': item['trainer_id'][1],
                'units_count': item['trainer_id_count']
            }
            for item in alloc_group if item['trainer_id']
        ]

        return {
            'kpis': {
                'total_trainers': total_trainers,
                'total_allocations': total_allocations,
                'schemes_approved': schemes_approved,
                'schemes_pending': schemes_pending,
                'workplans_completion_rate': round((workplans_done / workplans_total * 100), 1) if workplans_total else 0,
            },
            'trainer_workload': trainer_workload,
        }