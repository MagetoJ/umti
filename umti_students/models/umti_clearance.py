from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiGraduationClearance(models.Model):
    _name = 'umti.graduation.clearance'
    _description = 'Graduation Clearance'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'graduation_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    graduation_date = fields.Date()
    academic_year_id = fields.Many2one('umti.academic.year')
    finance_cleared = fields.Boolean()
    library_cleared = fields.Boolean()
    kits_cleared = fields.Boolean()
    discipline_cleared = fields.Boolean()
    accommodation_cleared = fields.Boolean()
    refund_amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    certificate_issued = fields.Boolean()
    state = fields.Selection([
        ('pending', 'Pending'), ('cleared', 'Cleared'),
        ('blocked', 'Blocked'),
    ], default='pending', required=True, tracking=True)

    @api.depends('student_id.name')
    def _compute_name(self):
        for record in self:
            record.name = _('Clearance - %s', record.student_id.name or '')

    def action_clear(self):
        self.write({'state': 'cleared'})

    def action_block(self):
        self.write({'state': 'blocked'})


class UmtiDashboardClearance(models.AbstractModel):
    _name = 'umti.dashboard.clearance'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Clearance Dashboard'
    AREA_CODE = 'clearance'
    AREA_MODEL = 'umti.graduation.clearance'
    AREA_LIST_VIEW = 'umti_students.umti_clearance_view_list'
    AREA_TITLE = 'Clearance & Graduation'
    AREA_SUBTITLE = 'Clearance blocks, refunds and certificates'
    AREA_GROUP = 'umti_students.group_umti_service_clearance'
    OPEN_STATES = ('pending', 'blocked')
    CLOSED_STATES = ('cleared',)



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    graduation_clearance_ids = fields.One2many('umti.graduation.clearance', 'student_id')

    def action_view_clearance(self):
        return self._view_area('umti.graduation.clearance', _('Clearance'), 'umti_students.umti_clearance_view_list')

    def action_new_clearance(self):
        return self._new_area_record('umti.graduation.clearance', _('New Clearance'))
