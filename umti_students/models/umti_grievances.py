from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiGrievanceCase(models.Model):
    _name = 'umti.grievance.case'
    _description = 'Student Grievance'
    _inherit = ['umti.student.record.mixin', 'umti.case.mixin',
                'mail.thread', 'mail.activity.mixin']
    _order = 'opened_date desc, id desc'

    name = fields.Char(string='Subject', required=True, tracking=True)
    category = fields.Selection([
        ('academic', 'Academic'), ('service', 'Service'),
        ('staff', 'Staff'), ('facility', 'Facility'), ('other', 'Other'),
    ], default='other', required=True)
    description = fields.Text()
    state = fields.Selection([
        ('new', 'New'), ('investigating', 'Investigating'),
        ('resolved', 'Resolved'), ('closed', 'Closed'),
    ], default='new', required=True, tracking=True)

    def action_investigate(self): self.write({'state': 'investigating'})
    def action_resolve(self): self.write({'state': 'resolved', 'closed_date': fields.Date.context_today(self)})
    def action_close(self): self.write({'state': 'closed', 'closed_date': fields.Date.context_today(self)})


class UmtiDashboardGrievances(models.AbstractModel):
    _name = 'umti.dashboard.grievances'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Grievances Dashboard'
    AREA_CODE = 'grievances'
    AREA_MODEL = 'umti.grievance.case'
    AREA_LIST_VIEW = 'umti_students.umti_grievance_case_view_list'
    AREA_TITLE = 'Grievances & Feedback'
    AREA_SUBTITLE = 'Complaints, investigation and resolution'
    AREA_GROUP = 'umti_students.group_umti_service_grievances'
    OPEN_STATES = ('new', 'investigating')
    CLOSED_STATES = ('resolved', 'closed')



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    grievance_case_ids = fields.One2many('umti.grievance.case', 'student_id')

    def action_view_grievances(self):
        return self._view_area('umti.grievance.case', _('Grievances'), 'umti_students.umti_grievance_case_view_list')

    def action_new_grievance_case(self):
        return self._new_area_record('umti.grievance.case', _('New Grievance'))
