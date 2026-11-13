from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiTransportRoute(models.Model):
    _name = 'umti.transport.route'
    _description = 'Transport Route'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char()
    capacity = fields.Integer(default=0)
    fee = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    subscription_ids = fields.One2many(
        'umti.transport.subscription', 'route_id', string='Subscriptions')


class UmtiTransportSubscription(models.Model):
    _name = 'umti.transport.subscription'
    _description = 'Transport Subscription'
    _rec_name = 'student_id'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    route_id = fields.Many2one(
        'umti.transport.route', string='Route', required=True,
        ondelete='restrict')
    stop = fields.Char()
    academic_year_id = fields.Many2one('umti.academic.year')
    academic_term_id = fields.Many2one('umti.academic.term')
    start_date = fields.Date(default=fields.Date.context_today)
    end_date = fields.Date()
    fee = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    state = fields.Selection([
        ('active', 'Active'), ('ended', 'Ended'), ('cancelled', 'Cancelled'),
    ], default='active', required=True, tracking=True)

    def action_end(self): self.write({'state': 'ended', 'end_date': fields.Date.context_today(self)})
    def action_cancel(self): self.write({'state': 'cancelled'})


class UmtiDashboardTransport(models.AbstractModel):
    _name = 'umti.dashboard.transport'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Transport Dashboard'
    AREA_CODE = 'transport'
    AREA_MODEL = 'umti.transport.subscription'
    AREA_LIST_VIEW = 'umti_students.umti_transport_subscription_view_list'
    AREA_TITLE = 'Transport'
    AREA_SUBTITLE = 'Routes, subscriptions and passes'
    AREA_GROUP = 'umti_students.group_umti_service_transport'
    OPEN_STATES = ('active',)
    CLOSED_STATES = ('ended', 'cancelled')
    EXTRA_FILTER_FIELD = 'route_id'
    EXTRA_FILTER_LABEL = 'Route'


    def _build(self, data):
        super()._build(data)
        data['actions'].append({'key': 'routes', 'label': 'Routes', 'icon': 'fa-bus'})

    def run_dashboard_action(self, action, filters=None):
        if action == 'routes':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': 'Transport Routes',
                'res_model': 'umti.transport.route',
                'view_mode': 'list,form',
                'views': [(self.env.ref('umti_students.umti_route_view_list').id, 'list'), (False, 'form')],
                'target': 'current',
            }}
        return super().run_dashboard_action(action, filters)



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    transport_subscription_ids = fields.One2many('umti.transport.subscription', 'student_id')

    def action_view_transport_subscriptions(self):
        return self._view_area('umti.transport.subscription', _('Transport'), 'umti_students.umti_transport_subscription_view_list')

    def action_new_transport_subscription(self):
        return self._new_area_record('umti.transport.subscription', _('New Transport Subscription'))
