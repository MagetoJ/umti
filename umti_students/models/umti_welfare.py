from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiWelfareRequest(models.Model):
    _name = 'umti.welfare.request'
    _description = 'Student Welfare Request'
    _inherit = ['umti.student.record.mixin', 'umti.case.mixin',
                'mail.thread', 'mail.activity.mixin']
    _order = 'opened_date desc, id desc'

    name = fields.Char(string='Request', required=True, tracking=True)
    category = fields.Selection([
        ('food', 'Food'), ('accommodation', 'Accommodation'),
        ('transport', 'Transport'), ('medical', 'Medical'),
        ('fees', 'Fees'), ('other', 'Other'),
    ], default='other', required=True)
    need = fields.Text()
    amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    approval_date = fields.Date()
    state = fields.Selection([
        ('new', 'New'), ('assessed', 'Assessed'),
        ('approved', 'Approved'), ('disbursed', 'Disbursed'),
        ('rejected', 'Rejected'), ('closed', 'Closed'),
    ], default='new', required=True, tracking=True)

    def action_assess(self): self.write({'state': 'assessed'})
    def action_approve(self):
        self.write({'state': 'approved', 'approval_date': fields.Date.context_today(self)})
    def action_disburse(self): self.write({'state': 'disbursed'})
    def action_reject(self): self.write({'state': 'rejected', 'closed_date': fields.Date.context_today(self)})
    def action_close(self): self.write({'state': 'closed', 'closed_date': fields.Date.context_today(self)})


class UmtiDashboardWelfare(models.AbstractModel):
    _name = 'umti.dashboard.welfare'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Student Welfare Dashboard'
    AREA_CODE = 'welfare'
    AREA_MODEL = 'umti.welfare.request'
    AREA_LIST_VIEW = 'umti_students.umti_welfare_request_view_list'
    AREA_TITLE = 'Student Welfare'
    AREA_SUBTITLE = 'Requests, assessment and support'
    AREA_GROUP = 'umti_students.group_umti_service_welfare'
    OPEN_STATES = ('new', 'assessed', 'approved')
    CLOSED_STATES = ('disbursed', 'rejected', 'closed')



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    welfare_request_ids = fields.One2many('umti.welfare.request', 'student_id')

    def action_view_welfare_requests(self):
        return self._view_area('umti.welfare.request', _('Welfare'), 'umti_students.umti_welfare_request_view_list')

    def action_new_welfare_request(self):
        return self._new_area_record('umti.welfare.request', _('New Welfare Request'))
