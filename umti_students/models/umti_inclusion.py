from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiStudentSupportPlan(models.Model):
    _name = 'umti.student.support.plan'
    _description = 'Student Support Plan'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'review_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    need_category = fields.Char(required=True)
    accommodations = fields.Text(required=True)
    review_date = fields.Date()
    confidential = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('active', 'Active'), ('closed', 'Closed'),
    ], default='draft', required=True, tracking=True)

    @api.depends('student_id.name', 'need_category')
    def _compute_name(self):
        for record in self:
            record.name = '%s - %s' % (
                record.student_id.name or '', record.need_category or '')

    def action_activate(self): self.write({'state': 'active'})
    def action_close(self): self.write({'state': 'closed'})


class UmtiDashboardInclusion(models.AbstractModel):
    _name = 'umti.dashboard.inclusion'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Inclusion Dashboard'
    AREA_CODE = 'inclusion'
    AREA_MODEL = 'umti.student.support.plan'
    AREA_LIST_VIEW = 'umti_students.umti_support_plan_view_list'
    AREA_TITLE = 'Special Needs & Inclusion'
    AREA_SUBTITLE = 'Support plans and accommodations'
    AREA_GROUP = 'umti_students.group_umti_service_inclusion'
    OPEN_STATES = ('draft', 'active')
    CLOSED_STATES = ('closed',)



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    support_plan_ids = fields.One2many('umti.student.support.plan', 'student_id')

    def action_view_support_plans(self):
        return self._view_area('umti.student.support.plan', _('Support Plans'), 'umti_students.umti_support_plan_view_list')

    def action_new_support_plan(self):
        return self._new_area_record('umti.student.support.plan', _('New Support Plan'))
