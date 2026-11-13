from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi


class UmtiAlumniProfile(models.Model):
    _name = 'umti.alumni.profile'
    _description = 'Alumni Profile'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'graduation_date desc, id desc'

    name = fields.Char(
        related='student_id.name', store=True, readonly=True)
    graduation_date = fields.Date(tracking=True)
    graduation_year = fields.Integer(
        compute='_compute_graduation_year', store=True)
    email = fields.Char(related='student_id.email', store=True)
    phone = fields.Char(related='student_id.phone', store=True)
    employment_status = fields.Selection([
        ('unknown', 'Unknown'),
        ('employed', 'Employed'),
        ('self_employed', 'Self-employed'),
        ('further_study', 'Further Study'),
        ('unemployed', 'Unemployed'),
    ], default='unknown', required=True, tracking=True)
    employer = fields.Char()
    job_title = fields.Char()
    further_study = fields.Char()
    engagement_status = fields.Selection([
        ('contactable', 'Contactable'),
        ('not_contactable', 'Not Contactable'),
        ('engaged', 'Engaged'),
    ], default='contactable', tracking=True)
    consent = fields.Boolean(
        string='Consent to Alumni Contact', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'umti_alumni_profile_attachment_rel', 'profile_id',
        'attachment_id', string='Attachments')

    _sql_constraints = [
        ('student_uniq', 'unique(student_id)',
         'A student can have only one alumni profile.'),
    ]

    @api.depends('graduation_date')
    def _compute_graduation_year(self):
        for profile in self:
            profile.graduation_year = (
                profile.graduation_date.year
                if profile.graduation_date else 0)


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    alumni_profile_ids = fields.One2many(
        'umti.alumni.profile', 'student_id', string='Alumni Profiles')

    def action_new_alumni_profile(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alumni Profile'),
            'res_model': 'umti.alumni.profile',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {'default_student_id': self.id},
            'target': 'current',
        }


class UmtiDashboardAlumni(models.AbstractModel):
    _name = 'umti.dashboard.alumni'
    _inherit = 'umti.dashboard.section'
    _description = 'Alumni Dashboard'

    DASH_TITLE = 'Alumni'
    DASH_SUBTITLE = 'Graduates, employment and engagement'

    @api.model
    def get_dashboard_data(self, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Alumni users can view this dashboard.'))
        return super().get_dashboard_data(filters=filters)

    def _can_read(self):
        return (
            self.env.user.has_group('umti_students.group_umti_service_alumni')
            or self.env.user.has_group('umti_students.group_umti_students_manager')
            or self.env.user.has_group('umti_students.group_umti_students_admin'))

    def _domain(self, filters):
        domain = [('company_id', 'in', self.env.companies.ids)]
        course_id = int(filters.get('course_id') or 0)
        if course_id:
            domain.append(('course_id', '=', course_id))
        year = int(filters.get('graduation_year') or 0)
        if year:
            domain.append(('graduation_year', '=', year))
        employment = filters.get('employment_status') or 'all'
        if employment != 'all':
            domain.append(('employment_status', '=', employment))
        engagement = filters.get('engagement_status') or 'all'
        if engagement != 'all':
            domain.append(('engagement_status', '=', engagement))
        return domain

    def _filter_definitions(self, filters):
        Profile = self.env['umti.alumni.profile']
        courses = self.env['umti.course'].search([
            ('active', '=', True), ('company_id', '=', self.env.company.id)],
            order='name')
        years = Profile.search(
            [('company_id', 'in', self.env.companies.ids)]
        ).mapped('graduation_year')
        year_options = [{'value': '', 'label': _('All')}] + [
            {'value': str(year), 'label': str(year)}
            for year in sorted({year for year in years if year}, reverse=True)
        ]
        employment_options = [{'value': 'all', 'label': _('All')}] + [
            {'value': key, 'label': label}
            for key, label in Profile._fields['employment_status'].selection
        ]
        engagement_options = [{'value': 'all', 'label': _('All')}] + [
            {'value': key, 'label': label}
            for key, label in Profile._fields['engagement_status'].selection
        ]
        return [
            {'key': 'course_id', 'label': _('Course'),
             'value': str(filters.get('course_id') or ''),
             'options': [{'value': '', 'label': _('All')}] + [
                 {'value': str(course.id), 'label': course.display_name}
                 for course in courses]},
            {'key': 'graduation_year', 'label': _('Graduation Year'),
             'value': str(filters.get('graduation_year') or ''),
             'options': year_options},
            {'key': 'employment_status', 'label': _('Employment'),
             'value': filters.get('employment_status') or 'all',
             'options': employment_options},
            {'key': 'engagement_status', 'label': _('Engagement'),
             'value': filters.get('engagement_status') or 'all',
             'options': engagement_options},
        ]

    def _build(self, data):
        filters = data.get('active_filters') or {}
        data['filters'] = self._filter_definitions(filters)
        data['actions'] = [
            {'key': 'new_profile', 'label': _('New Profile'),
             'icon': 'fa-plus'},
            {'key': 'profiles', 'label': _('All Alumni'),
             'icon': 'fa-list'},
        ]
        domain = self._domain(filters)
        Profile = self.env['umti.alumni.profile']
        profiles = Profile.search(domain)
        employed = profiles.filtered(
            lambda profile: profile.employment_status in (
                'employed', 'self_employed'))
        further = profiles.filtered(
            lambda profile: profile.employment_status == 'further_study')
        engaged = profiles.filtered(
            lambda profile: profile.engagement_status == 'engaged')
        contactable = profiles.filtered(
            lambda profile: profile.engagement_status != 'not_contactable')
        data['kpis'] = [
            _kpi('alumni_total', 'Alumni', len(profiles), 'fa-users',
                 'Graduates on record', 'blue',
                 model='umti.alumni.profile', domain=domain),
            _kpi('alumni_contactable', 'Contactable', len(contactable),
                 'fa-phone', 'Not marked lost', 'green',
                 model='umti.alumni.profile', domain=domain),
            _kpi('alumni_employed', 'Employed', len(employed),
                 'fa-briefcase', 'Employed or self-employed', 'violet',
                 model='umti.alumni.profile',
                 domain=domain + [('employment_status', 'in',
                                   ('employed', 'self_employed'))]),
            _kpi('alumni_study', 'Further Study', len(further),
                 'fa-graduation-cap', 'Continuing education', 'amber',
                 model='umti.alumni.profile',
                 domain=domain + [('employment_status', '=', 'further_study')]),
            _kpi('alumni_engaged', 'Engaged', len(engaged),
                 'fa-heart', 'Actively engaged alumni', 'green',
                 model='umti.alumni.profile',
                 domain=domain + [('engagement_status', '=', 'engaged')]),
        ]
        items, more = self._group_items(
            'umti.alumni.profile', 'employment_status', domain, None,
            limit=6)
        data['charts'] = [{
            'key': 'alumni_employment',
            'title': _('Employment status'),
            'type': 'bars',
            'items': items,
            'more': more,
        }]
        missing_employer = profiles.filtered(
            lambda profile: profile.employment_status == 'employed'
            and not profile.employer)[:6]
        recent = profiles.sorted(
            lambda profile: profile.graduation_date or fields.Date.today(),
            reverse=True)[:6]
        data['lists'] = [
            {
                'key': 'alumni_recent',
                'title': _('Recent graduates'),
                'rows': [{
                    'label': profile.name,
                    'meta': '%s · %s' % (
                        profile.course_id.name,
                        profile.graduation_date or ''),
                    'badge': profile.employment_status.replace('_', ' ').title(),
                    'tone': 'blue',
                    'model': 'umti.alumni.profile',
                    'res_id': profile.id,
                } for profile in recent],
            },
            {
                'key': 'alumni_missing',
                'title': _('Employment details missing'),
                'rows': [{
                    'label': profile.name,
                    'meta': profile.course_id.name,
                    'badge': 'Employer missing',
                    'tone': 'amber',
                    'model': 'umti.alumni.profile',
                    'res_id': profile.id,
                } for profile in missing_employer],
            },
        ]

    @api.model
    def run_dashboard_action(self, action, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Alumni users can run this action.'))
        filters = filters or {}
        if action == 'profiles':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('Alumni'),
                'res_model': 'umti.alumni.profile',
                'view_mode': 'list,form',
                'views': [(
                    self.env.ref('umti_students.umti_alumni_profile_view_list').id,
                    'list'), (False, 'form')],
                'domain': self._domain(filters),
                'target': 'current',
            }}
        if action == 'new_profile':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('Alumni Profile'),
                'res_model': 'umti.alumni.profile',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }}
        raise UserError(_('Unknown Alumni action.'))
