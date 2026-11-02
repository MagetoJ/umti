from odoo import http
from odoo.http import request


class KitsDashboardController(http.Controller):

    @http.route('/umti/dashboard/kits_data', type='json', auth='user')
    def get_kits_dashboard_data(self):
        env = request.env

        total_kits = env['umti.kits'].search_count([])
        active_issuances = env['umti.kits.issuance'].search_count([('state', '=', 'issued')])
        returned_issuances = env['umti.kits.issuance'].search_count([('state', '=', 'returned')])
        overdue_issuances = env['umti.kits.issuance'].search_count([('state', '=', 'overdue')])

        # Condition breakdown
        issuance_records = env['umti.kits.issuance'].search_read([], ['return_condition'])
        conditions = {'good': 0, 'damaged': 0, 'lost': 0}
        for rec in issuance_records:
            cond = rec.get('return_condition')
            if cond in conditions:
                conditions[cond] += 1

        # Issuances by Kit
        kit_group = env['umti.kits.issuance'].read_group(
            domain=[],
            fields=['kit_id'],
            groupby=['kit_id']
        )
        issuances_by_kit = [
            {
                'kit_name': item['kit_id'][1],
                'count': item['kit_id_count']
            }
            for item in kit_group if item['kit_id']
        ]

        return {
            'kpis': {
                'total_kits': total_kits,
                'active_issuances': active_issuances,
                'returned_issuances': returned_issuances,
                'overdue_issuances': overdue_issuances,
            },
            'conditions': conditions,
            'issuances_by_kit': issuances_by_kit,
        }