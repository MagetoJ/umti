from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi

class UmtiStudentClub(models.Model):
    _name = 'umti.student.club'
    _description = 'Student Club'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char()
    category = fields.Char()
    description = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    membership_ids = fields.One2many(
        'umti.club.membership', 'club_id', string='Memberships')


class UmtiClubMembership(models.Model):
    _name = 'umti.club.membership'
    _description = 'Club Membership'
    _rec_name = 'student_id'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'joined_date desc, id desc'

    club_id = fields.Many2one(
        'umti.student.club', string='Club', required=True,
        ondelete='cascade')
    role = fields.Char()
    joined_date = fields.Date(default=fields.Date.context_today)
    left_date = fields.Date()
    state = fields.Selection([
        ('active', 'Active'), ('left', 'Left'), ('cancelled', 'Cancelled'),
    ], default='active', required=True, tracking=True)

    def action_leave(self): self.write({'state': 'left', 'left_date': fields.Date.context_today(self)})
    def action_cancel(self): self.write({'state': 'cancelled'})


class UmtiDashboardActivities(models.AbstractModel):
    _name = 'umti.dashboard.activities'
    _inherit = 'umti.dashboard.student.area'
    _description = 'Activities Dashboard'
    AREA_CODE = 'activities'
    AREA_MODEL = 'umti.club.membership'
    AREA_LIST_VIEW = 'umti_students.umti_club_membership_view_list'
    AREA_TITLE = 'Student Activities'
    AREA_SUBTITLE = 'Clubs, memberships and participation'
    AREA_GROUP = 'umti_students.group_umti_service_activities'
    OPEN_STATES = ('active',)
    CLOSED_STATES = ('left', 'cancelled')

    def _build(self, data):
        super()._build(data)
        data['actions'].append({'key': 'clubs', 'label': 'Clubs', 'icon': 'fa-users'})

    def run_dashboard_action(self, action, filters=None):
        if action == 'clubs':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': 'Clubs',
                'res_model': 'umti.student.club',
                'view_mode': 'list,form',
                'views': [(self.env.ref('umti_students.umti_club_view_list').id, 'list'), (False, 'form')],
                'target': 'current',
            }}
        return super().run_dashboard_action(action, filters)



class SchoolStudent(models.Model):
    _inherit = 'school.student'

    club_membership_ids = fields.One2many('umti.club.membership', 'student_id')

    def action_view_club_memberships(self):
        return self._view_area('umti.club.membership', _('Club Memberships'), 'umti_students.umti_club_membership_view_list')

    def action_new_club_membership(self):
        return self._new_area_record('umti.club.membership', _('New Club Membership'))
