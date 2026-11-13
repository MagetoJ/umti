from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi


class UmtiDashboardStudentArea(models.AbstractModel):
    _name = 'umti.dashboard.student.area'
    _inherit = 'umti.dashboard.section'
    _description = 'Student Area Dashboard Base'

    AREA_CODE = ''
    AREA_MODEL = ''
    AREA_LIST_VIEW = ''
    AREA_TITLE = ''
    AREA_SUBTITLE = ''
    AREA_GROUP = ''
    OPEN_STATES = ()
    CLOSED_STATES = ()
    STATE_FILTER = True
    EXTRA_FILTER_FIELD = ''
    EXTRA_FILTER_LABEL = ''

    @api.model
    def get_dashboard_data(self, filters=None):
        if not self._can_read():
            raise AccessError(_('Only the responsible team can view this dashboard.'))
        return super().get_dashboard_data(filters=filters)

    def _can_read(self):
        return (
            self.env.user.has_group(self.AREA_GROUP)
            or self.env.user.has_group('umti_students.group_umti_students_manager')
            or self.env.user.has_group('umti_students.group_umti_students_admin'))

    def _domain(self, filters):
        domain = [('company_id', 'in', self.env.companies.ids)]
        model = self.env[self.AREA_MODEL]
        if 'course_id' in model._fields:
            course_id = int(filters.get('course_id') or 0)
            if course_id:
                domain.append(('course_id', '=', course_id))
        if self.STATE_FILTER:
            state = filters.get('state') or 'all'
            if state != 'all':
                domain.append(('state', '=', state))
        if self.EXTRA_FILTER_FIELD:
            value = int(filters.get('extra') or 0)
            if value:
                domain.append((self.EXTRA_FILTER_FIELD, '=', value))
        return domain

    def _filter_definitions(self, filters):
        model = self.env[self.AREA_MODEL]
        filters_list = []
        if 'course_id' in model._fields:
            courses = self.env['umti.course'].search([
                ('active', '=', True),
                ('company_id', '=', self.env.company.id)], order='name')
            filters_list.append({
                'key': 'course_id', 'label': _('Course'),
                'value': str(filters.get('course_id') or ''),
                'options': [{'value': '', 'label': _('All')}] + [
                    {'value': str(course.id), 'label': course.display_name}
                    for course in courses]})
        if self.STATE_FILTER and 'state' in model._fields:
            options = [{'value': 'all', 'label': _('All')}]
            options += [
                {'value': key, 'label': label}
                for key, label in model._fields['state'].selection
            ]
            filters_list.append({
                'key': 'state', 'label': _('State'),
                'value': filters.get('state') or 'all',
                'options': options})
        if self.EXTRA_FILTER_FIELD:
            comodel = model._fields[self.EXTRA_FILTER_FIELD].comodel_name
            records = self.env[comodel].search([], limit=100)
            filters_list.append({
                'key': 'extra', 'label': self.EXTRA_FILTER_LABEL,
                'value': str(filters.get('extra') or ''),
                'options': [{'value': '', 'label': _('All')}] + [
                    {'value': str(record.id), 'label': record.display_name}
                    for record in records]})
        return filters_list

    def _build(self, data):
        filters = data.get('active_filters') or {}
        data['filters'] = self._filter_definitions(filters)
        data['actions'] = [
            {'key': 'new', 'label': _('New Record'), 'icon': 'fa-plus'},
            {'key': 'records', 'label': _('All Records'), 'icon': 'fa-list'},
        ]
        domain = self._domain(filters)
        model = self.env[self.AREA_MODEL]
        records = model.search(domain)
        open_records = records.filtered(
            lambda record: getattr(record, 'state', False)
            and record.state in self.OPEN_STATES)
        closed_records = records.filtered(
            lambda record: getattr(record, 'state', False)
            and record.state in self.CLOSED_STATES)
        data['kpis'] = [
            _kpi(self.AREA_CODE + '_total', _('Total'), len(records),
                 'fa-folder-o', self.AREA_SUBTITLE or '', 'blue',
                 model=self.AREA_MODEL, domain=domain),
            _kpi(self.AREA_CODE + '_open', _('Open'), len(open_records),
                 'fa-folder-open-o', 'Awaiting action',
                 'amber' if open_records else 'green',
                 model=self.AREA_MODEL,
                 domain=domain + [('state', 'in', self.OPEN_STATES)]
                 if self.STATE_FILTER else domain),
            _kpi(self.AREA_CODE + '_closed', _('Closed'), len(closed_records),
                 'fa-check-circle', 'Completed records', 'green',
                 model=self.AREA_MODEL,
                 domain=domain + [('state', 'in', self.CLOSED_STATES)]
                 if self.STATE_FILTER else domain),
        ]
        self._extra_kpis(data, records, domain)
        if self.STATE_FILTER and 'state' in model._fields:
            items, more = self._group_items(
                self.AREA_MODEL, 'state', domain, None, limit=8)
            data['charts'] = [{
                'key': self.AREA_CODE + '_states',
                'title': _('Records by state'),
                'type': 'bars',
                'items': items,
                'more': more,
            }]
        recent = records.sorted('create_date', reverse=True)[:6]
        data['lists'] = [{
            'key': self.AREA_CODE + '_recent',
            'title': _('Recent records'),
            'rows': [{
                'label': record.display_name,
                'meta': getattr(record.student_id, 'display_name', ''),
                'badge': (getattr(record, 'state', '') or '').replace('_', ' ').title(),
                'tone': 'blue',
                'model': self.AREA_MODEL,
                'res_id': record.id,
            } for record in recent],
        }]

    def _extra_kpis(self, data, records, domain):
        pass

    @api.model
    def run_dashboard_action(self, action, filters=None):
        if not self._can_read():
            raise AccessError(_('Only the responsible team can run this action.'))
        filters = filters or {}
        if action == 'records':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': self.AREA_TITLE,
                'res_model': self.AREA_MODEL,
                'view_mode': 'list,form',
                'views': [(
                    self.env.ref(self.AREA_LIST_VIEW).id, 'list'),
                    (False, 'form')],
                'domain': self._domain(filters),
                'target': 'current',
            }}
        if action == 'new':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': self.AREA_TITLE,
                'res_model': self.AREA_MODEL,
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }}
        raise UserError(_('Unknown action.'))

