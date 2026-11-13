from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiClinicVisit(models.Model):
    _name = 'umti.clinic.visit'
    _description = 'Clinic Visit'
    _rec_name = 'student_id'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'visit_date desc, id desc'

    visit_date = fields.Date(default=fields.Date.context_today, required=True)
    complaint = fields.Text(required=True)
    diagnosis = fields.Text()
    treatment = fields.Text()
    referred_to = fields.Char()
    insurance_claim = fields.Char()
    claim_status = fields.Selection([
        ('none', 'None'), ('pending', 'Pending'),
        ('approved', 'Approved'), ('rejected', 'Rejected'),
    ], default='none')
    confidential = fields.Boolean(default=True)
    state = fields.Selection([
        ('open', 'Open'), ('closed', 'Closed'),
    ], default='open', required=True, tracking=True)

    def action_close(self): self.write({'state': 'closed'})


class UmtiDashboardClinic(models.AbstractModel):
    _name = 'umti.dashboard.health'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Clinic Dashboard'
    AREA_CODE = 'health'
    AREA_MODEL = 'umti.clinic.visit'
    AREA_LIST_VIEW = 'umti_students.umti_clinic_visit_view_list'
    AREA_TITLE = 'Health & Clinic'
    AREA_SUBTITLE = 'Visits, treatment and insurance claims'
    AREA_GROUP = 'umti_students.group_umti_service_health'
    OPEN_STATES = ('open',)
    CLOSED_STATES = ('closed',)



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    clinic_visit_ids = fields.One2many('umti.clinic.visit', 'student_id')

    def action_view_clinic_visits(self):
        return self._view_area('umti.clinic.visit', _('Clinic Visits'), 'umti_students.umti_clinic_visit_view_list')

    def action_new_clinic_visit(self):
        return self._new_area_record('umti.clinic.visit', _('New Clinic Visit'))
