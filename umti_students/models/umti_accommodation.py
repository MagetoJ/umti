from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi


class UmtiHostel(models.Model):
    _name = 'umti.hostel'
    _description = 'Hostel'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char()
    capacity = fields.Integer(default=0)
    active = fields.Boolean(default=True)
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    allocation_ids = fields.One2many(
        'umti.hostel.allocation', 'hostel_id', string='Allocations')

    def _occupied(self, year=None):
        domain = [('hostel_id', 'in', self.ids), ('state', '=', 'checked_in')]
        if year:
            domain.append(('academic_year_id', '=', year.id))
        return self.env['umti.hostel.allocation'].search_count(domain)


class UmtiHostelAllocation(models.Model):
    _name = 'umti.hostel.allocation'
    _description = 'Hostel Allocation'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'check_in desc, id desc'
    _rec_name = 'student_id'

    hostel_id = fields.Many2one(
        'umti.hostel', string='Hostel', required=True,
        ondelete='restrict', tracking=True)
    room = fields.Char()
    bed = fields.Char()
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', tracking=True)
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', tracking=True)
    check_in = fields.Date(tracking=True)
    check_out = fields.Date(tracking=True)
    state = fields.Selection([
        ('reserved', 'Reserved'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('cancelled', 'Cancelled'),
    ], default='reserved', required=True, tracking=True)
    fee = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    def action_check_in(self):
        self.write({
            'state': 'checked_in',
            'check_in': self.check_in or fields.Date.context_today(self),
        })

    def action_check_out(self):
        self.write({
            'state': 'checked_out',
            'check_out': fields.Date.context_today(self),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    hostel_allocation_ids = fields.One2many(
        'umti.hostel.allocation', 'student_id', string='Hostel Allocations')

    def action_new_hostel_allocation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Hostel Allocation'),
            'res_model': 'umti.hostel.allocation',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {'default_student_id': self.id},
            'target': 'current',
        }


class UmtiDashboardAccommodation(models.AbstractModel):
    _name = 'umti.dashboard.accommodation'
    _inherit = 'umti.dashboard.section'
    _description = 'Accommodation Dashboard'

    DASH_TITLE = 'Accommodation'
    DASH_SUBTITLE = 'Hostel capacity, occupancy and check-ins'

    @api.model
    def get_dashboard_data(self, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Accommodation users can view this dashboard.'))
        return super().get_dashboard_data(filters=filters)

    def _can_read(self):
        return (
            self.env.user.has_group('umti_students.group_umti_service_accommodation')
            or self.env.user.has_group('umti_students.group_umti_students_manager')
            or self.env.user.has_group('umti_students.group_umti_students_admin'))

    def _domain(self, filters):
        domain = [('company_id', 'in', self.env.companies.ids)]
        hostel_id = int(filters.get('hostel_id') or 0)
        if hostel_id:
            domain.append(('hostel_id', '=', hostel_id))
        state = filters.get('state') or 'all'
        if state != 'all':
            domain.append(('state', '=', state))
        course_id = int(filters.get('course_id') or 0)
        if course_id:
            domain.append(('course_id', '=', course_id))
        return domain

    def _filter_definitions(self, filters):
        Hostel = self.env['umti.hostel']
        Allocation = self.env['umti.hostel.allocation']
        hostels = Hostel.search([
            ('active', '=', True), ('company_id', '=', self.env.company.id)],
            order='name')
        courses = self.env['umti.course'].search([
            ('active', '=', True), ('company_id', '=', self.env.company.id)],
            order='name')
        states = [{'value': 'all', 'label': _('All')}] + [
            {'value': key, 'label': label}
            for key, label in Allocation._fields['state'].selection
        ]
        return [
            {'key': 'hostel_id', 'label': _('Hostel'),
             'value': str(filters.get('hostel_id') or ''),
             'options': [{'value': '', 'label': _('All')}] + [
                 {'value': str(hostel.id), 'label': hostel.name}
                 for hostel in hostels]},
            {'key': 'course_id', 'label': _('Course'),
             'value': str(filters.get('course_id') or ''),
             'options': [{'value': '', 'label': _('All')}] + [
                 {'value': str(course.id), 'label': course.display_name}
                 for course in courses]},
            {'key': 'state', 'label': _('Allocation State'),
             'value': filters.get('state') or 'all',
             'options': states},
        ]

    def _build(self, data):
        filters = data.get('active_filters') or {}
        data['filters'] = self._filter_definitions(filters)
        data['actions'] = [
            {'key': 'new_allocation', 'label': _('New Allocation'),
             'icon': 'fa-plus'},
            {'key': 'allocations', 'label': _('All Allocations'),
             'icon': 'fa-list'},
            {'key': 'hostels', 'label': _('Hostels'), 'icon': 'fa-building-o'},
        ]
        domain = self._domain(filters)
        Allocation = self.env['umti.hostel.allocation']
        allocations = Allocation.search(domain)
        hostels = self.env['umti.hostel'].search([
            ('active', '=', True), ('company_id', '=', self.env.company.id)])
        beds = sum(hostels.mapped('capacity'))
        occupied = allocations.filtered(
            lambda allocation: allocation.state == 'checked_in')
        reserved = allocations.filtered(
            lambda allocation: allocation.state == 'reserved')
        vacant = max(beds - len(occupied), 0)
        rate = (100.0 * len(occupied) / beds) if beds else 0.0
        data['kpis'] = [
            _kpi('hostel_beds', 'Beds', beds, 'fa-bed', 'Configured capacity',
                 'blue', model='umti.hostel', domain=[
                     ('active', '=', True),
                     ('company_id', 'in', self.env.companies.ids)]),
            _kpi('hostel_occupied', 'Occupied', len(occupied),
                 'fa-user-check', 'Checked-in students', 'green',
                 model='umti.hostel.allocation',
                 domain=domain + [('state', '=', 'checked_in')]),
            _kpi('hostel_reserved', 'Reserved', len(reserved),
                 'fa-hourglass-o', 'Beds held', 'amber',
                 model='umti.hostel.allocation',
                 domain=domain + [('state', '=', 'reserved')]),
            _kpi('hostel_vacant', 'Vacant', vacant, 'fa-bed',
                 'Available beds', 'violet',
                 model='umti.hostel.allocation',
                 domain=domain + [('state', '=', 'checked_in')]),
            _kpi('hostel_rate', 'Occupancy', '%d%%' % round(rate),
                 'fa-percent', '%d of %d beds occupied' % (
                     len(occupied), beds),
                 'green' if rate >= 80 else ('amber' if rate else 'red'),
                 model='umti.hostel.allocation',
                 domain=domain + [('state', '=', 'checked_in')]),
        ]
        items, more = self._group_items(
            'umti.hostel.allocation', 'hostel_id',
            domain + [('state', '=', 'checked_in')], None, limit=8)
        data['charts'] = [{
            'key': 'hostel_by_hostel',
            'title': _('Checked-in students by hostel'),
            'type': 'bars',
            'items': items,
            'more': more,
        }]
        current = occupied.sorted(
            lambda allocation: allocation.hostel_id.name)[:6]
        data['lists'] = [{
            'key': 'hostel_current',
            'title': _('Current residents'),
            'rows': [{
                'label': allocation.student_id.display_name,
                'meta': '%s · %s / %s' % (
                    allocation.hostel_id.name,
                    allocation.room or '-', allocation.bed or '-'),
                'badge': allocation.state.replace('_', ' ').title(),
                'tone': 'green',
                'model': 'umti.hostel.allocation',
                'res_id': allocation.id,
            } for allocation in current],
        }]

    @api.model
    def run_dashboard_action(self, action, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Accommodation users can run this action.'))
        filters = filters or {}
        if action == 'allocations':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('Hostel Allocations'),
                'res_model': 'umti.hostel.allocation',
                'view_mode': 'list,form',
                'views': [(
                    self.env.ref(
                        'umti_students.umti_hostel_allocation_view_list').id,
                    'list'), (False, 'form')],
                'domain': self._domain(filters),
                'target': 'current',
            }}
        if action == 'hostels':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('Hostels'),
                'res_model': 'umti.hostel',
                'view_mode': 'list,form',
                'views': [(
                    self.env.ref('umti_students.umti_hostel_view_list').id,
                    'list'), (False, 'form')],
                'target': 'current',
            }}
        if action == 'new_allocation':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('New Hostel Allocation'),
                'res_model': 'umti.hostel.allocation',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }}
        raise UserError(_('Unknown Accommodation action.'))
