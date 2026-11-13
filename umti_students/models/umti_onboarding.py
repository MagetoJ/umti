from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiStudentOnboarding(models.Model):
    _name = 'umti.student.onboarding'
    _description = 'Student Onboarding'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(compute='_compute_name', store=True)
    academic_year_id = fields.Many2one('umti.academic.year')
    intake_id = fields.Many2one('school.admission.intake')
    id_card_issued = fields.Boolean()
    photo_captured = fields.Boolean()
    documents_complete = fields.Boolean()
    orientation_complete = fields.Boolean()
    portal_access = fields.Boolean()
    state = fields.Selection([
        ('pending', 'Pending'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], default='pending', required=True, tracking=True)

    @api.depends('student_id.name')
    def _compute_name(self):
        for record in self:
            record.name = _('Onboarding - %s', record.student_id.name or '')

    def action_complete(self): self.write({'state': 'completed'})


class UmtiDashboardOnboarding(models.AbstractModel):
    _name = 'umti.dashboard.onboarding'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Onboarding Dashboard'
    AREA_CODE = 'onboarding'
    AREA_MODEL = 'umti.student.onboarding'
    AREA_LIST_VIEW = 'umti_students.umti_onboarding_view_list'
    AREA_TITLE = 'Student ID & Onboarding'
    AREA_SUBTITLE = 'ID, documents, orientation and portal access'
    AREA_GROUP = 'umti_students.group_umti_service_onboarding'
    OPEN_STATES = ('pending', 'in_progress')
    CLOSED_STATES = ('completed',)



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    onboarding_ids = fields.One2many('umti.student.onboarding', 'student_id')

    def action_view_onboarding(self):
        return self._view_area('umti.student.onboarding', _('Onboarding'), 'umti_students.umti_onboarding_view_list')

    def action_new_onboarding(self):
        return self._new_area_record('umti.student.onboarding', _('New Onboarding'))
