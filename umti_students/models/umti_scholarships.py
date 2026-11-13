from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi


class UmtiScholarshipAward(models.Model):
    _name = 'umti.scholarship.award'
    _description = 'Scholarship or Sponsorship Award'
    _inherit = ['umti.student.record.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Award', required=True, tracking=True)
    reference = fields.Char()
    award_type = fields.Selection([
        ('scholarship', 'Scholarship'),
        ('bursary', 'Bursary'),
        ('sponsorship', 'Sponsorship'),
        ('other', 'Other'),
    ], default='scholarship', required=True, tracking=True)
    sponsor_type = fields.Selection([
        ('government', 'Government'),
        ('corporate', 'Corporate'),
        ('ngo', 'NGO / Foundation'),
        ('individual', 'Individual'),
        ('internal', 'Internal'),
    ], default='internal', required=True)
    sponsor = fields.Char(required=True, tracking=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', tracking=True)
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', tracking=True)
    start_date = fields.Date(tracking=True)
    end_date = fields.Date(tracking=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    amount = fields.Monetary(currency_field='currency_id', tracking=True)
    disbursed_amount = fields.Monetary(
        currency_field='currency_id', tracking=True)
    disbursement_date = fields.Date(tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('disbursed', 'Disbursed'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'umti_scholarship_award_attachment_rel',
        'award_id', 'attachment_id', string='Attachments')

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_disburse(self):
        self.write({
            'state': 'disbursed',
            'disbursement_date': fields.Date.context_today(self),
            'disbursed_amount': self.disbursed_amount or self.amount,
        })

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    scholarship_award_ids = fields.One2many(
        'umti.scholarship.award', 'student_id', string='Scholarships')

    def action_new_scholarship_award(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Scholarship'),
            'res_model': 'umti.scholarship.award',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {'default_student_id': self.id},
            'target': 'current',
        }


class UmtiDashboardScholarships(models.AbstractModel):
    _name = 'umti.dashboard.scholarships'
    _inherit = 'umti.dashboard.section'
    _description = 'Scholarships Dashboard'

    DASH_TITLE = 'Scholarships & Sponsorship'
    DASH_SUBTITLE = 'Awards, sponsors and disbursements'

    @api.model
    def get_dashboard_data(self, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Scholarships users can view this dashboard.'))
        return super().get_dashboard_data(filters=filters)

    def _can_read(self):
        return (
            self.env.user.has_group('umti_students.group_umti_service_scholarships')
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
        award_type = filters.get('award_type') or 'all'
        if award_type != 'all':
            domain.append(('award_type', '=', award_type))
        return domain

    def _filter_definitions(self, filters):
        Award = self.env['umti.scholarship.award']
        courses = self.env['umti.course'].search([
            ('active', '=', True), ('company_id', '=', self.env.company.id)],
            order='name')
        states = [{'value': 'all', 'label': _('All')}] + [
            {'value': key, 'label': label}
            for key, label in Award._fields['state'].selection
        ]
        types = [{'value': 'all', 'label': _('All')}] + [
            {'value': key, 'label': label}
            for key, label in Award._fields['award_type'].selection
        ]
        return [
            {'key': 'course_id', 'label': _('Course'),
             'value': str(filters.get('course_id') or ''),
             'options': [{'value': '', 'label': _('All')}] + [
                 {'value': str(course.id), 'label': course.display_name}
                 for course in courses]},
            {'key': 'award_type', 'label': _('Award Type'),
             'value': filters.get('award_type') or 'all',
             'options': types},
            {'key': 'state', 'label': _('State'),
             'value': filters.get('state') or 'all',
             'options': states},
        ]

    def _money(self, value):
        symbol = self.env.company.currency_id.symbol or ''
        return '%s%s' % (symbol, '{:,.0f}'.format(value or 0))

    def _build(self, data):
        filters = data.get('active_filters') or {}
        data['filters'] = self._filter_definitions(filters)
        data['actions'] = [
            {'key': 'new_award', 'label': _('New Award'), 'icon': 'fa-plus'},
            {'key': 'awards', 'label': _('All Awards'), 'icon': 'fa-list'},
        ]
        domain = self._domain(filters)
        Award = self.env['umti.scholarship.award']
        awards = Award.search(domain)
        active = awards.filtered(
            lambda award: award.state in ('approved', 'active'))
        disbursed = sum(awards.mapped('disbursed_amount'))
        total = sum(awards.mapped('amount'))
        pending = max(total - disbursed, 0)
        students = len(awards.mapped('student_id'))
        data['kpis'] = [
            _kpi('scholarships_total', 'Awards', len(awards),
                 'fa-graduation-cap', 'On record', 'blue',
                 model='umti.scholarship.award', domain=domain),
            _kpi('scholarships_students', 'Students Covered', students,
                 'fa-users', 'Distinct students', 'violet',
                 model='umti.scholarship.award', domain=domain),
            _kpi('scholarships_active', 'Active', len(active),
                 'fa-check-circle', 'Approved or active', 'green',
                 model='umti.scholarship.award',
                 domain=domain + [('state', 'in', ('approved', 'active'))]),
            _kpi('scholarships_awarded', 'Total Awarded',
                 self._money(total), 'fa-money', 'All awards', 'blue',
                 model='umti.scholarship.award', domain=domain),
            _kpi('scholarships_pending', 'Pending Disbursement',
                 self._money(pending), 'fa-hourglass-o', 'Still to pay',
                 'amber' if pending else 'green',
                 model='umti.scholarship.award', domain=domain),
        ]
        items, more = self._group_items(
            'umti.scholarship.award', 'award_type', domain, None, limit=6)
        data['charts'] = [{
            'key': 'scholarships_type',
            'title': _('Awards by type'),
            'type': 'bars',
            'items': items,
            'more': more,
        }]
        recent = awards.sorted(
            lambda award: award.start_date or fields.Date.today(),
            reverse=True)[:6]
        pending_awards = awards.filtered(
            lambda award: award.state not in ('disbursed', 'closed', 'cancelled')
            and award.amount > award.disbursed_amount)[:6]
        data['lists'] = [
            {
                'key': 'scholarships_recent',
                'title': _('Recent awards'),
                'rows': [{
                    'label': award.student_id.display_name,
                    'meta': '%s · %s' % (award.name, award.sponsor),
                    'badge': award.state.replace('_', ' ').title(),
                    'tone': 'blue',
                    'model': 'umti.scholarship.award',
                    'res_id': award.id,
                } for award in recent],
            },
            {
                'key': 'scholarships_pending_list',
                'title': _('Pending disbursement'),
                'rows': [{
                    'label': award.student_id.display_name,
                    'meta': award.sponsor,
                    'badge': self._money(award.amount - award.disbursed_amount),
                    'tone': 'amber',
                    'model': 'umti.scholarship.award',
                    'res_id': award.id,
                } for award in pending_awards],
            },
        ]

    @api.model
    def run_dashboard_action(self, action, filters=None):
        if not self._can_read():
            raise AccessError(_('Only Scholarships users can run this action.'))
        filters = filters or {}
        if action == 'awards':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('Scholarships'),
                'res_model': 'umti.scholarship.award',
                'view_mode': 'list,form',
                'views': [(
                    self.env.ref(
                        'umti_students.umti_scholarship_award_view_list').id,
                    'list'), (False, 'form')],
                'domain': self._domain(filters),
                'target': 'current',
            }}
        if action == 'new_award':
            return {'action': {
                'type': 'ir.actions.act_window',
                'name': _('New Scholarship'),
                'res_model': 'umti.scholarship.award',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }}
        raise UserError(_('Unknown Scholarships action.'))
