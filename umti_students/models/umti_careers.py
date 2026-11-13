from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi


class UmtiStudentAttachment(models.Model):
    _name = 'umti.student.attachment'
    _description = 'Student Attachment'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    _rec_name = 'employer'

    employer = fields.Char(required=True, tracking=True)
    supervisor = fields.Char()
    supervisor_phone = fields.Char()
    placement_type = fields.Selection([
        ('industrial', 'Industrial Attachment'),
        ('field', 'Field Attachment'),
        ('internship', 'Internship'),
        ('work', 'Work Placement'),
    ], default='industrial', required=True)
    start_date = fields.Date(tracking=True)
    end_date = fields.Date(tracking=True)
    visit_date = fields.Date()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Placement'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    assessment = fields.Text()
    logbook_summary = fields.Text()
    attachment_ids = fields.Many2many(
        'ir.attachment', 'umti_student_attachment_attachment_rel',
        'attachment_id', 'file_id', string='Attachments')

    def action_start(self):
        self.write({'state': 'active'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reopen(self):
        self.write({'state': 'draft'})


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    attachment_ids = fields.One2many(
        'umti.student.attachment', 'student_id', string='Attachments')

    def action_new_attachment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Attachment'),
            'res_model': 'umti.student.attachment',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {'default_student_id': self.id},
            'target': 'current',
        }


class UmtiDashboardCareers(models.AbstractModel):
    _name = 'umti.dashboard.careers'
    _inherit = 'umti.dashboard.section'
    _description = 'Careers and Attachment Dashboard'

    DASH_TITLE = 'Careers & Attachment'
    DASH_SUBTITLE = 'Placements, employers and attachment progress'

    @api.model
    def get_dashboard_data(self, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Careers users can view this dashboard.'))
        return super().get_dashboard_data(filters=filters)

    def _can_read(self):
        return (
            self.env.user.has_group('umti_students.group_umti_service_careers')
            or self.env.user.has_group('umti_students.group_umti_students_manager')
            or self.env.user.has_group('umti_students.group_umti_students_admin'))

    def _domain(self, filters):
        domain = [('company_id', 'in', self.env.companies.ids)]
        course_id = int(filters.get('course_id') or 0)
        if course_id:
            domain.append(('course_id', '=', course_id))
        state = filters.get('state') or 'all'
        if state != 'all':
            domain.append(('state', '=', state))
        placement = filters.get('placement_type') or 'all'
        if placement != 'all':
            domain.append(('placement_type', '=', placement))
        return domain

    def _filter_definitions(self, filters):
        Profile = self.env['umti.student.attachment']
        courses = self.env['umti.course'].search([
            ('active', '=', True), ('company_id', '=', self.env.company.id)],
            order='name')
        state_options = [{'value': 'all', 'label': _('All')}] + [
            {'value': key, 'label': label}
            for key, label in Profile._fields['state'].selection
        ]
        placement_options = [{'value': 'all', 'label': _('All')}] + [
            {'value': key, 'label': label}
            for key, label in Profile._fields['placement_type'].selection
        ]
        return [
            {'key': 'course_id', 'label': _('Course'),
             'value': str(filters.get('course_id') or ''),
             'options': [{'value': '', 'label': _('All')}] + [
                 {'value': str(course.id), 'label': course.display_name}
                 for course in courses]},
            {'key': 'state', 'label': _('Attachment State'),
             'value': filters.get('state') or 'all',
             'options': state_options},
            {'key': 'placement_type', 'label': _('Placement Type'),
             'value': filters.get('placement_type') or 'all',
             'options': placement_options},
        ]

    def _build(self, data):
        filters = data.get('active_filters') or {}
        data['filters'] = self._filter_definitions(filters)
        data['actions'] = [
            {'key': 'new_attachment', 'label': _('New Attachment'),
             'icon': 'fa-plus'},
            {'key': 'attachments', 'label': _('All Attachments'),
             'icon': 'fa-list'},
        ]
        domain = self._domain(filters)
        Attachment = self.env['umti.student.attachment']
        attachments = Attachment.search(domain)
        pending = attachments.filtered(lambda record: record.state == 'pending')
        active = attachments.filtered(lambda record: record.state == 'active')
        completed = attachments.filtered(
            lambda record: record.state == 'completed')
        data['kpis'] = [
            _kpi('careers_total', 'Placements', len(attachments),
                 'fa-briefcase', 'On record', 'blue',
                 model='umti.student.attachment', domain=domain),
            _kpi('careers_pending', 'Pending', len(pending), 'fa-hourglass-o',
                 'Awaiting placement', 'amber',
                 model='umti.student.attachment',
                 domain=domain + [('state', '=', 'pending')]),
            _kpi('careers_active', 'Active', len(active), 'fa-play-circle',
                 'Currently on attachment', 'violet',
                 model='umti.student.attachment',
                 domain=domain + [('state', '=', 'active')]),
            _kpi('careers_completed', 'Completed', len(completed),
                 'fa-check-circle', 'Finished placements', 'green',
                 model='umti.student.attachment',
                 domain=domain + [('state', '=', 'completed')]),
            _kpi('careers_employers', 'Employers',
                 len({record.employer for record in attachments if record.employer}),
                 'fa-building-o', 'Distinct employers', 'blue',
                 model='umti.student.attachment', domain=domain),
        ]
        items, more = self._group_items(
            'umti.student.attachment', 'state', domain, None, limit=6)
        data['charts'] = [{
            'key': 'careers_state',
            'title': _('Attachment state'),
            'type': 'bars',
            'items': items,
            'more': more,
        }]
        recent = attachments.sorted(
            lambda record: record.start_date or fields.Date.today(),
            reverse=True)[:6]
        data['lists'] = [{
            'key': 'careers_recent',
            'title': _('Recent attachments'),
            'rows': [{
                'label': record.student_id.display_name,
                'meta': '%s · %s' % (record.employer, record.supervisor or ''),
                'badge': record.state.replace('_', ' ').title(),
                'tone': 'blue',
                'model': 'umti.student.attachment',
                'res_id': record.id,
            } for record in recent],
        }]

    @api.model
    def run_dashboard_action(self, action, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Careers users can run this action.'))
        filters = filters or {}
        if action == 'attachments':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('Attachments'),
                'res_model': 'umti.student.attachment',
                'view_mode': 'list,form',
                'views': [(
                    self.env.ref(
                        'umti_students.umti_attachment_view_list').id,
                    'list'), (False, 'form')],
                'domain': self._domain(filters),
                'target': 'current',
            }}
        if action == 'new_attachment':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('New Attachment'),
                'res_model': 'umti.student.attachment',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }}
        raise UserError(_('Unknown Careers action.'))
