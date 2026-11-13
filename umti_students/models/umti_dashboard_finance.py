from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.umti_core.models.umti_dashboard import _kpi


class UmtiDashboardFinance(models.AbstractModel):
    _name = 'umti.dashboard.finance'
    _inherit = 'umti.dashboard.section'
    _description = 'Student Finance Dashboard'

    DASH_TITLE = 'Student Finance'
    DASH_SUBTITLE = 'Billing and collections for active semesters'

    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        if not self.env.user.has_group(
                'umti_students.group_umti_student_finance'):
            raise AccessError(_(
                'Only Student Finance users can view this dashboard.'))
        return super().get_dashboard_data(filters=filters)

    @api.model
    def run_dashboard_action(self, action, filters=None):
        if not self.env.user.has_group(
                'umti_students.group_umti_student_finance'):
            raise AccessError(_(
                'Only Student Finance users can run this action.'))
        record = self._finance_record(filters or {})
        if not record:
            raise UserError(_('Select an academic year first.'))
        try:
            if action == 'invoices':
                return {'action': {
                    'type': 'ir.actions.act_window',
                    'name': _('Student Invoices'),
                    'res_model': 'account.move',
                    'view_mode': 'list,form',
                    'views': [(
                        self.env.ref(
                            'umti_students.umti_student_invoice_view_list').id,
                        'list'), (False, 'form')],
                    'domain': record._invoice_domain(),
                    'target': 'current',
                }}
            if action == 'payments':
                students = record._target_students()
                return {'action': {
                    'type': 'ir.actions.act_window',
                    'name': _('Student Payments'),
                    'res_model': 'account.payment',
                    'view_mode': 'list,form',
                    'views': [(
                        self.env.ref(
                            'umti_students.umti_student_payment_view_list').id,
                        'list'), (False, 'form')],
                    'domain': [('umti_student_id', 'in', students.ids)],
                    'target': 'current',
                }}
            if action == 'generate':
                record.action_generate_invoices()
            else:
                raise UserError(_('Unknown Student Finance action.'))
            message = record.last_run_summary or _('Done.')
        finally:
            record.unlink()
        return {'message': message, 'type': 'success'}

    # ------------------------------------------------------------------
    def _record_vals(self, filters):
        Year = self.env['umti.academic.year']
        year = Year.browse(int(filters.get('academic_year_id') or 0))
        if not year:
            year = Year.search([
                ('status', '=', 'running'), ('active', '=', True),
            ], order='start_date desc', limit=1)
        if not year:
            year = Year.search(
                [('active', '=', True)], order='start_date desc', limit=1)
        if not year:
            return False
        course_id = int(filters.get('course_id') or 0)
        intake_id = int(filters.get('intake_id') or 0)
        states = [
            key for key, _label in self.env[
                'school.student']._fields['state'].selection]
        state = filters.get('student_state') or 'active'
        if state != 'all' and state not in states:
            state = 'active'
        return {
            'academic_year_id': year.id,
            'course_id': course_id or False,
            'intake_id': intake_id or False,
            'student_state': state,
            'company_id': self.env.company.id,
        }

    def _finance_record(self, filters):
        vals = self._record_vals(filters)
        if not vals:
            return False
        return self.env['umti.student.finance'].create(vals)

    def _options(self, records, all_label=_('All')):
        options = [{'value': '', 'label': all_label}]
        options += [
            {'value': str(record.id), 'label': record.display_name}
            for record in records
        ]
        return options

    def _filter_definitions(self, record):
        Year = self.env['umti.academic.year']
        Course = self.env['umti.course']
        Intake = self.env['school.admission.intake']
        Student = self.env['school.student']
        years = Year.search(
            [('active', '=', True)], order='start_date desc')
        year_options = [
            {'value': str(year.id), 'label': year.display_name}
            for year in years
        ]
        state_options = [{'value': 'all', 'label': _('All')}]
        state_options += [
            {'value': key, 'label': label}
            for key, label in Student._fields['state'].selection
        ]
        courses = Course.search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id),
        ], order='name')
        intakes = Intake.search([
            ('company_id', '=', self.env.company.id),
            ('state', '!=', 'cancelled'),
        ], order='date_open desc')
        return [
            {'key': 'academic_year_id', 'label': _('Academic Year'),
             'value': str(record.academic_year_id.id),
             'options': year_options},
            {'key': 'course_id', 'label': _('Course'),
             'value': str(record.course_id.id) if record.course_id else '',
             'options': self._options(courses)},
            {'key': 'intake_id', 'label': _('Intake'),
             'value': str(record.intake_id.id) if record.intake_id else '',
             'options': self._options(intakes)},
            {'key': 'student_state', 'label': _('Student State'),
             'value': record.student_state,
             'options': state_options},
        ]

    def _money(self, record, value):
        symbol = record.currency_id.symbol or ''
        return '%s%s' % (symbol, '{:,.0f}'.format(value or 0))

    # ------------------------------------------------------------------
    def _build(self, data):
        record = self._finance_record(data.get('active_filters') or {})
        if not record:
            data['kpis'] = [
                _kpi('no_year', 'Academic year', '—', 'fa-calendar',
                     'Create or activate an academic year first.')]
            return
        try:
            data['filters'] = self._filter_definitions(record)
            data['actions'] = [
                {'key': 'invoices', 'label': _('Student Invoices'),
                 'icon': 'fa-file-text-o'},
                {'key': 'payments', 'label': _('Student Payments'),
                 'icon': 'fa-credit-card'},
                {'key': 'generate', 'label': _('Generate Invoices'),
                 'icon': 'fa-plus',
                 'confirm': _('Create and post semester invoices for every '
                              'active student in this scope?')},
            ]
            invoice_domain = record._invoice_domain()
            posted_domain = invoice_domain + [('state', '=', 'posted')]
            students = record._target_students()
            collection_rate = (
                (100.0 * record.paid_total / record.invoiced_total)
                if record.invoiced_total else 0.0)
            payment_domain = [
                ('umti_student_id', 'in', students.ids),
                ('state', '=', 'posted'),
            ]
            data['kpis'] = [
                _kpi('finance_students', 'Students',
                     record.student_count, 'fa-users',
                     '%d in scope' % record.student_count, 'blue',
                     model='school.student',
                     domain=record._student_domain()),
                _kpi('finance_invoiced', 'Invoiced',
                     self._money(record, record.invoiced_total),
                     'fa-file-text-o',
                     '%d semester invoice(s)' % record.semester_invoice_count,
                     'violet', model='account.move',
                     domain=posted_domain),
                _kpi('finance_paid', 'Paid',
                     self._money(record, record.paid_total), 'fa-money',
                     '%d paid, %d with a balance' % (
                         record.paid_count,
                         record.partial_count + record.unpaid_count),
                     'green', model='account.move', domain=posted_domain),
                _kpi('finance_outstanding', 'Outstanding',
                     self._money(record, record.outstanding_total),
                     'fa-exclamation-circle',
                     '%d unpaid or partial' % (
                         record.partial_count + record.unpaid_count),
                     'red' if record.outstanding_total else 'green',
                     model='account.move', domain=posted_domain),
                _kpi('finance_collection', 'Collection Rate',
                     '%d%%' % round(collection_rate), 'fa-percent',
                     '%s collected of %s' % (
                         self._money(record, record.paid_total),
                         self._money(record, record.invoiced_total)),
                     'green' if collection_rate >= 80
                     else ('amber' if collection_rate >= 50 else 'red'),
                     model='account.move', domain=posted_domain),
                _kpi('finance_payments', 'Payments',
                     record.payment_count, 'fa-credit-card',
                     self._money(record, record.payment_total),
                     'blue', model='account.payment',
                     domain=payment_domain),
            ]
            data['charts'] = [{
                'key': 'finance_status',
                'title': _('Semester invoice status'),
                'type': 'donut',
                'items': [
                    self._item(
                        _('Paid'), record.paid_count, 'account.move',
                        posted_domain + [('payment_state', '=', 'paid')]),
                    self._item(
                        _('Partial / in payment'), record.partial_count,
                        'account.move',
                        posted_domain + [
                            ('payment_state', 'in',
                             ('partial', 'in_payment'))]),
                    self._item(
                        _('Unpaid'), record.unpaid_count, 'account.move',
                        posted_domain + [
                            ('payment_state', 'in',
                             ('not_paid', 'blocked'))]),
                ],
            }]
            outstanding = self.env['account.move'].search(
                posted_domain + [('amount_residual', '>', 0)],
                order='amount_residual desc', limit=6)
            recent_payments = self.env['account.payment'].search(
                payment_domain, order='date desc', limit=6)
            data['lists'] = [
                {
                    'key': 'finance_outstanding_invoices',
                    'title': _('Largest outstanding balances'),
                    'rows': [{
                        'label': move.umti_student_id.display_name
                                 or move.partner_id.name,
                        'meta': '%s · %s' % (
                            move.name,
                            move.umti_academic_term_id.name or ''),
                        'badge': self._money(move, move.amount_residual),
                        'tone': 'red',
                        'model': 'account.move',
                        'res_id': move.id,
                    } for move in outstanding],
                },
                {
                    'key': 'finance_recent_payments',
                    'title': _('Recent payments'),
                    'rows': [{
                        'label': payment.umti_student_id.display_name
                                 or payment.partner_id.name,
                        'meta': '%s · %s' % (
                            payment.date, payment.journal_id.name or ''),
                        'badge': self._money(payment, payment.amount),
                        'tone': 'green',
                        'model': 'account.payment',
                        'res_id': payment.id,
                    } for payment in recent_payments],
                },
            ]
        finally:
            record.unlink()
