from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi


class UmtiDashboardStudentServices(models.AbstractModel):
    _name = 'umti.dashboard.student_services'
    _inherit = 'umti.dashboard.section'
    _description = 'Student Services Dashboard'

    DASH_TITLE = 'Student Services'
    DASH_SUBTITLE = 'Guidance, welfare, discipline, careers and campus services'

    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        if not self.env.user.has_group(
                'umti_students.group_umti_student_services_user'):
            raise AccessError(_(
                'Only Student Services users can view this dashboard.'))
        return super().get_dashboard_data(filters=filters)

    def _is_manager(self):
        return (
            self.env.user.has_group(
                'umti_students.group_umti_students_manager')
            or self.env.user.has_group(
                'umti_students.group_umti_students_admin'))

    def _allowed_types(self):
        types = self.env['umti.student.service.type'].search(
            [('active', '=', True)], order='sequence, name')
        if self._is_manager():
            return types
        return types.filtered(
            lambda service: any(
                group in self.env.user.groups_id
                for group in service.group_ids))

    def _case_domain(self, filters):
        types = self._allowed_types()
        domain = [
            ('company_id', 'in', self.env.companies.ids),
            ('service_type_id', 'in', types.ids),
        ]
        service_id = int(filters.get('service_type_id') or 0)
        if service_id and service_id in types.ids:
            domain.append(('service_type_id', '=', service_id))
        course_id = int(filters.get('course_id') or 0)
        if course_id:
            domain.append(('course_id', '=', course_id))
        student_state = filters.get('student_state') or 'all'
        if student_state != 'all':
            domain.append(('student_state', '=', student_state))
        state = filters.get('state') or 'all'
        if state != 'all':
            domain.append(('state', '=', state))
        priority = filters.get('priority') or 'all'
        if priority != 'all':
            domain.append(('priority', '=', priority))
        return domain

    def _options(self, records):
        return [{'value': '', 'label': _('All')}] + [
            {'value': str(record.id), 'label': record.display_name}
            for record in records
        ]

    def _filter_definitions(self, filters):
        types = self._allowed_types()
        courses = self.env['umti.course'].search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id),
        ], order='name')
        students = self.env['school.student']
        cases = self.env['umti.student.service.case']
        student_states = [{'value': 'all', 'label': _('All')}]
        student_states += [
            {'value': key, 'label': label}
            for key, label in students._fields['state'].selection
        ]
        case_states = [{'value': 'all', 'label': _('All')}]
        case_states += [
            {'value': key, 'label': label}
            for key, label in cases._fields['state'].selection
        ]
        priorities = [{'value': 'all', 'label': _('All')}]
        priorities += [
            {'value': key, 'label': label}
            for key, label in cases._fields['priority'].selection
        ]
        return [
            {'key': 'service_type_id', 'label': _('Service'),
             'value': str(filters.get('service_type_id') or ''),
             'options': self._options(types)},
            {'key': 'course_id', 'label': _('Course'),
             'value': str(filters.get('course_id') or ''),
             'options': self._options(courses)},
            {'key': 'student_state', 'label': _('Student State'),
             'value': filters.get('student_state') or 'all',
             'options': student_states},
            {'key': 'state', 'label': _('Case State'),
             'value': filters.get('state') or 'all',
             'options': case_states},
            {'key': 'priority', 'label': _('Priority'),
             'value': filters.get('priority') or 'all',
             'options': priorities},
        ]

    # ------------------------------------------------------------------
    def _build(self, data):
        filters = data.get('active_filters') or {}
        data['filters'] = self._filter_definitions(filters)
        data['actions'] = [
            {'key': 'new_case', 'label': _('New Case'),
             'icon': 'fa-plus'},
            {'key': 'cases', 'label': _('All Cases'),
             'icon': 'fa-list'},
        ]
        domain = self._case_domain(filters)
        open_domain = domain + [
            ('state', 'in', ('new', 'in_progress', 'on_hold'))]
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        resolved_domain = domain + [
            ('closed_date', '>=', month_start),
            ('state', 'in', ('resolved', 'closed')),
        ]
        Case = self.env['umti.student.service.case']
        open_cases = Case.search(open_domain, order='create_date desc')
        data['kpis'] = [
            _kpi('services_open', 'Open Cases', len(open_cases),
                 'fa-folder-open-o', 'Across visible services', 'blue',
                 model='umti.student.service.case', domain=open_domain),
            _kpi('services_new', 'New',
                 len(open_cases.filtered(lambda case: case.state == 'new')),
                 'fa-inbox', 'Not started yet', 'amber',
                 model='umti.student.service.case',
                 domain=open_domain + [('state', '=', 'new')]),
            _kpi('services_progress', 'In Progress',
                 len(open_cases.filtered(
                     lambda case: case.state == 'in_progress')),
                 'fa-spinner', 'Being handled', 'violet',
                 model='umti.student.service.case',
                 domain=open_domain + [('state', '=', 'in_progress')]),
            _kpi('services_urgent', 'High / Urgent',
                 len(open_cases.filtered(
                     lambda case: case.priority in ('high', 'urgent'))),
                 'fa-exclamation-circle', 'Open priority cases', 'red',
                 model='umti.student.service.case',
                 domain=open_domain + [
                     ('priority', 'in', ('high', 'urgent'))]),
            _kpi('services_resolved', 'Resolved This Month',
                 Case.search_count(resolved_domain), 'fa-check-circle',
                 'Closed since the first of the month', 'green',
                 model='umti.student.service.case', domain=resolved_domain),
        ]
        items, more = self._group_items(
            'umti.student.service.case', 'service_type_id', open_domain,
            None, limit=8)
        data['charts'] = [{
            'key': 'services_by_type',
            'title': _('Open cases by service'),
            'type': 'bars',
            'items': items,
            'more': more,
        }]
        urgent = open_cases.filtered(
            lambda case: case.priority in ('high', 'urgent'))[:6]
        recent = open_cases[:6]
        data['lists'] = [
            {
                'key': 'services_recent',
                'title': _('Recent open cases'),
                'rows': [{
                    'label': case.name,
                    'meta': '%s · %s' % (
                        case.student_id.display_name,
                        case.service_type_id.name),
                    'badge': case.state.replace('_', ' ').title(),
                    'tone': 'amber',
                    'model': 'umti.student.service.case',
                    'res_id': case.id,
                } for case in recent],
            },
            {
                'key': 'services_urgent_list',
                'title': _('High priority cases'),
                'rows': [{
                    'label': case.name,
                    'meta': '%s · %s' % (
                        case.student_id.display_name,
                        case.service_type_id.name),
                    'badge': case.priority.title(),
                    'tone': 'red',
                    'model': 'umti.student.service.case',
                    'res_id': case.id,
                } for case in urgent],
            },
        ]

    # ------------------------------------------------------------------
    @api.model
    def run_dashboard_action(self, action, filters=None):
        if not self.env.user.has_group(
                'umti_students.group_umti_student_services_user'):
            raise AccessError(_(
                'Only Student Services users can run this action.'))
        filters = filters or {}
        domain = self._case_domain(filters)
        if action == 'cases':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('Student Services'),
                'res_model': 'umti.student.service.case',
                'view_mode': 'list,form',
                'views': [(
                    self.env.ref(
                        'umti_students.umti_student_service_case_view_list').id,
                    'list'), (False, 'form')],
                'domain': domain,
                'target': 'current',
            }}
        if action == 'new_case':
            service_id = int(filters.get('service_type_id') or 0)
            if not service_id:
                allowed = self._allowed_types()
                service_id = allowed[:1].id
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('New Service Case'),
                'res_model': 'umti.student.service.case',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'context': {
                    'default_service_type_id': service_id,
                    'default_assigned_to': self.env.user.id,
                },
                'target': 'current',
            }}
        raise UserError(_('Unknown Student Services action.'))
