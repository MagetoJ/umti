from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiDisciplineCase(models.Model):
    _name = 'umti.discipline.case'
    _description = 'Discipline Case'
    _inherit = ['umti.student.record.mixin', 'umti.case.mixin',
                'mail.thread', 'mail.activity.mixin']
    _order = 'opened_date desc, id desc'

    name = fields.Char(string='Incident', required=True, tracking=True)
    incident_type = fields.Selection([
        ('attendance', 'Attendance'), ('conduct', 'Conduct'),
        ('academic', 'Academic'), ('property', 'Property'), ('other', 'Other'),
    ], default='conduct', required=True)
    description = fields.Text()
    hearing_date = fields.Date()
    decision = fields.Text()
    sanction = fields.Text()
    state = fields.Selection([
        ('new', 'New'), ('hearing', 'Hearing'),
        ('decided', 'Decided'), ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='new', required=True, tracking=True)

    def action_schedule_hearing(self): self.write({'state': 'hearing'})
    def action_decide(self): self.write({'state': 'decided'})
    def action_close(self): self.write({'state': 'closed', 'closed_date': fields.Date.context_today(self)})
    def action_cancel(self): self.write({'state': 'cancelled', 'closed_date': fields.Date.context_today(self)})


class UmtiDashboardDiscipline(models.AbstractModel):
    _name = 'umti.dashboard.discipline'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Discipline Dashboard'
    AREA_CODE = 'discipline'
    AREA_MODEL = 'umti.discipline.case'
    AREA_LIST_VIEW = 'umti_students.umti_discipline_case_view_list'
    AREA_TITLE = 'Discipline'
    AREA_SUBTITLE = 'Incidents, hearings and decisions'
    AREA_GROUP = 'umti_students.group_umti_service_discipline'
    OPEN_STATES = ('new', 'hearing', 'decided')
    CLOSED_STATES = ('closed', 'cancelled')



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    discipline_case_ids = fields.One2many('umti.discipline.case', 'student_id')

    def action_view_discipline_cases(self):
        return self._view_area('umti.discipline.case', _('Discipline'), 'umti_students.umti_discipline_case_view_list')

    def action_new_discipline_case(self):
        return self._new_area_record('umti.discipline.case', _('New Discipline Case'))
