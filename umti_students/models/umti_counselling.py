from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiCounsellingCase(models.Model):
    _name = 'umti.counselling.case'
    _description = 'Counselling Case'
    _inherit = ['umti.student.record.mixin', 'umti.case.mixin',
                'mail.thread', 'mail.activity.mixin']
    _order = 'opened_date desc, id desc'

    name = fields.Char(string='Subject', required=True, tracking=True)
    category = fields.Selection([
        ('academic', 'Academic'), ('personal', 'Personal'),
        ('career', 'Career'), ('health', 'Health'), ('other', 'Other'),
    ], default='personal')
    risk_level = fields.Selection([
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'),
    ], default='low', required=True)
    state = fields.Selection([
        ('new', 'New'), ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'), ('closed', 'Closed'),
    ], default='new', required=True, tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'umti_counselling_attachment_rel', 'case_id',
        'attachment_id', string='Attachments')

    def action_start(self): self.write({'state': 'in_progress'})
    def action_resolve(self): self.write({'state': 'resolved', 'closed_date': fields.Date.context_today(self)})
    def action_close(self): self.write({'state': 'closed', 'closed_date': fields.Date.context_today(self)})


class UmtiDashboardCounselling(models.AbstractModel):
    _name = 'umti.dashboard.counselling'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Counselling Dashboard'
    AREA_CODE = 'counselling'
    AREA_MODEL = 'umti.counselling.case'
    AREA_LIST_VIEW = 'umti_students.umti_counselling_case_view_list'
    AREA_TITLE = 'Guidance & Counselling'
    AREA_SUBTITLE = 'Cases, follow-ups and referrals'
    AREA_GROUP = 'umti_students.group_umti_service_counselling'
    OPEN_STATES = ('new', 'in_progress')
    CLOSED_STATES = ('resolved', 'closed')



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    counselling_case_ids = fields.One2many('umti.counselling.case', 'student_id')

    def action_view_counselling_cases(self):
        return self._view_area('umti.counselling.case', _('Counselling'), 'umti_students.umti_counselling_case_view_list')

    def action_new_counselling_case(self):
        return self._new_area_record('umti.counselling.case', _('New Counselling Case'))
