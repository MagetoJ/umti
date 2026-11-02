import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UmtiTrainerAllocation(models.Model):
    _name = 'umti.trainer.allocation'
    _description = 'Trainers'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    trainer_name = fields.Char(
        string='Trainer Name', required=True, tracking=True)
    trainer_email = fields.Char(string='Email', tracking=True)
    trainer_phone = fields.Char(string='Phone', tracking=True)
    department_id = fields.Many2one(
        'umti.department', string='Department', required=True, tracking=True)
    course_ids = fields.Many2many(
        'umti.course', 'trainer_allocation_course_rel',
        'allocation_id', 'course_id', string='Courses', required=True,
        domain="[('department_id', '=', department_id)]")
    unit_ids = fields.Many2many(
        'umti.course.units', 'trainer_allocation_unit_rel',
        'allocation_id', 'unit_id', string='Units', required=True,
        domain="[('id', 'in', allowed_unit_ids)]")
    allowed_unit_ids = fields.Many2many(
        'umti.course.units', compute='_compute_allowed_unit_ids')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('retired', 'Retired'),
    ], string='Status', default='draft', required=True, tracking=True,
        copy=False,
        help="Draft: particulars being captured. Approved: the employee, "
             "portal user and contract exist. Retired: contracts closed and "
             "employee archived.")

    # Employment particulars: pushed to the hr.employee created on save
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', readonly=True, copy=False,
        tracking=True, ondelete='restrict')
    job_id = fields.Many2one(
        'hr.job', string='Job Position', tracking=True)
    contract_id = fields.Many2one(
        'hr.contract', string='Contract', readonly=True, copy=False,
        tracking=True)
    contract_start_date = fields.Date(
        string='Contract Start', tracking=True)
    contract_end_date = fields.Date(
        string='Contract End', tracking=True)
    wage = fields.Monetary(
        string='Wage', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', related='company_id.currency_id')

    # Fields whose change must be pushed to the employee / contract
    _HR_SYNC_FIELDS = {
        'trainer_name', 'trainer_email', 'trainer_phone',
        'company_id', 'job_id',
        'contract_start_date', 'contract_end_date', 'wage',
    }

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('course_ids', 'course_ids.unit_ids')
    def _compute_allowed_unit_ids(self):
        for rec in self:
            rec.allowed_unit_ids = rec.course_ids.unit_ids

    @api.depends('trainer_name', 'department_id', 'department_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (
                rec.trainer_name or '',
                rec.department_id.name or '')

    @api.constrains('course_ids', 'department_id')
    def _check_courses_in_department(self):
        for rec in self:
            bad = rec.course_ids.filtered(lambda c: c.department_id != rec.department_id)
            if bad:
                raise ValidationError(_(
                    "These courses do not belong to department %s: %s",
                    rec.department_id.name,
                    ', '.join(bad.mapped('name'))))

    @api.onchange('department_id')
    def _onchange_department_id(self):
        self.course_ids = False
        self.unit_ids = False

    @api.onchange('course_ids')
    def _onchange_course_ids(self):
        if self.course_ids:
            allowed = self.course_ids.unit_ids
            self.unit_ids = self.unit_ids & allowed
        else:
            self.unit_ids = False

    @api.constrains('contract_start_date', 'contract_end_date')
    def _check_contract_dates(self):
        for rec in self:
            if (rec.contract_start_date and rec.contract_end_date
                    and rec.contract_end_date < rec.contract_start_date):
                raise ValidationError(_(
                    "Contract end date cannot be earlier than the contract "
                    "start date."))

    # ------------------------------------------------------------------
    # Approval flow
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # A trainer is captured in draft; the employee is only created when
        # the record is approved.
        for vals in vals_list:
            vals.setdefault('state', 'draft')
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if self._HR_SYNC_FIELDS & set(vals):
            # Only approved trainers have an employee/contract to keep in sync.
            self.filtered(
                lambda r: r.state == 'approved')._sync_trainer()
        if 'unit_ids' in vals:
            self.filtered(
                lambda r: r.state == 'approved')._assign_units_for_running_term()
        return res

    def action_approve(self):
        """Approve the trainer: create/link the employee, its portal user and
        the contract carrying the particulars."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Trainer %(name)s is not in draft, it cannot be approved.",
                    name=rec.display_name))
            if not rec.trainer_name:
                raise UserError(_("Set the trainer name before approving."))
            if rec.employee_id and not rec.employee_id.active:
                rec.employee_id.sudo().write({'active': True})
            rec._sync_trainer()
            rec.write({'state': 'approved'})
            rec._assign_units_for_running_term()

    def _assign_units_for_running_term(self):
        """Staff this trainer's units for the term that is running.

        ``umti.unit.trainer`` is what enrollments, timetables and the trainer
        workspace read from; approving an allocation has to fill it in,
        otherwise the Unit Trainers list stays empty while the trainer is
        clearly allocated to the units.
        """
        Assignment = self.env['umti.unit.trainer'].sudo()
        Term = self.env['umti.academic.term'].sudo()
        for rec in self:
            units = rec.unit_ids.filtered('active')
            if not units or not rec.employee_id:
                continue
            term = Term.search([
                ('company_id', '=', rec.company_id.id),
                ('parent_term', '=', False),
                ('status', '=', 'in_progress'),
            ], limit=1)
            if not term:
                # Nothing can be assigned before a term is running.
                continue
            already = Assignment.search([
                ('unit_id', 'in', units.ids),
                ('academic_term_id', '=', term.id),
            ]).unit_id
            missing = units - already
            if not missing:
                continue
            Assignment.with_context(
                skip_trainer_allocation_check=True,
            ).create([{
                'unit_id': unit.id,
                'trainer_id': rec.employee_id.id,
                'academic_year_id': term.academic_year_id.id,
                'academic_term_id': term.id,
                'company_id': rec.company_id.id,
            } for unit in missing])

    def action_retire(self):
        """Retire the trainer: close the contracts and archive the employee."""
        today = fields.Date.context_today(self)
        Contract = self.env['hr.contract'].sudo()
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_(
                    "Trainer %(name)s is not approved, it cannot be retired.",
                    name=rec.display_name))
            employee = rec.employee_id.sudo()
            if employee:
                contracts = Contract.search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ('draft', 'open')),
                ])
                close_vals = {'date_end': today}
                if 'close' in dict(Contract._fields['state'].selection):
                    close_vals['state'] = 'close'
                contracts.write(close_vals)
                employee.write({'active': False})
            rec.write({'state': 'retired'})

    def action_set_draft(self):
        """Return a retired trainer to draft so the flow can be restarted.

        The employee and its contracts are left untouched; approving again
        reactivates them.
        """
        for rec in self:
            if rec.state == 'draft':
                continue
            rec.write({'state': 'draft'})

    def _run_contract(self, contract):
        """Move a contract from *New* to *Running*.

        Approving a trainer is the act that puts the contract in force, yet
        ``hr.contract`` is created in ``draft`` and nothing else transitions
        it. Prefer the model's own transition method when a version exposes
        one, then fall back to the state write. Contracts that are already
        running (or finished) are left untouched.
        """
        if not contract:
            return contract
        Contract = contract.sudo()
        try:
            states = dict(Contract._fields['state']._description_selection(
                self.env))
        except AttributeError:
            states = {}
        running = next(
            (key for key in ('open', 'running') if key in states), None)
        if not running or Contract.state in (running,) + ('close', 'cancel'):
            return contract
        try:
            for method in ('action_open', 'action_running'):
                transition = getattr(Contract, method, None)
                if callable(transition):
                    transition()
                    if Contract.state == running:
                        return contract
                    break
            if Contract.state != running:
                Contract.write({'state': running})
        except Exception as error:  # noqa: BLE001 - never block the approval
            _logger.warning(
                "Contract %s could not be set to %s: %s",
                Contract.id, running, error)
        return contract

    def _prepare_employee_vals(self, vals):
        """Map the allocation particulars onto hr.employee values."""
        employee_vals = {
            'name': vals.get('trainer_name'),
            'company_id': vals.get('company_id') or self.env.company.id,
        }
        if vals.get('trainer_email'):
            employee_vals['work_email'] = vals['trainer_email']
        if vals.get('trainer_phone'):
            employee_vals['work_phone'] = vals['trainer_phone']
        if vals.get('job_id'):
            employee_vals['job_id'] = vals['job_id']
        return employee_vals

    def _get_or_create_employee(self, vals):
        """Return the employee for these trainer particulars, creating it the
        first time a trainer is allocated."""
        Employee = self.env['hr.employee'].sudo()
        employee = Employee
        email = vals.get('trainer_email')
        if email:
            employee = Employee.with_context(active_test=False).search(
                [('work_email', '=', email)], limit=1)
        if not employee:
            employee = Employee.create(self._prepare_employee_vals(vals))
        return employee

    def _ensure_portal_user(self, employee):
        """Return the employee's user, creating a portal user when missing."""
        if employee.user_id:
            return employee.user_id
        Users = self.env['res.users'].sudo()
        portal_group = self.env.ref('base.group_portal')
        # Odoo 18 renamed address_id to work_contact_id
        partner = employee.work_contact_id if 'work_contact_id' in employee._fields \
            else employee.address_id
        vals = {
            'name': employee.name,
            'login': employee.work_email or 'trainer.%s' % employee.id,
            'email': employee.work_email or False,
            'share': True,
            'company_id': employee.company_id.id or self.env.company.id,
            'partner_id': partner.id if partner else False,
        }
        # Odoo 18 renamed groups_id to group_ids
        group_field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        vals[group_field] = [(6, 0, [portal_group.id])]
        user = Users.create(vals)
        employee.write({'user_id': user.id})
        return user

    def _sync_trainer(self):
        """Push the trainer particulars to the employee, give it a portal
        user and a matching hr.contract."""
        if self.env.context.get('umti_skip_trainer_sync'):
            return
        Contract = self.env['hr.contract'].sudo()
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.trainer_name:
                # Nothing to push yet (e.g. a half-migrated row).
                continue
            vals = {
                'trainer_name': rec.trainer_name,
                'trainer_email': rec.trainer_email,
                'trainer_phone': rec.trainer_phone,
                'job_id': rec.job_id.id,
                'company_id': rec.company_id.id,
            }
            employee = rec.employee_id.sudo() or rec._get_or_create_employee(
                vals)
            employee.write(rec._prepare_employee_vals(vals))

            rec._ensure_portal_user(employee)

            start = rec.contract_start_date or today
            contract = rec.contract_id
            if contract and (contract.employee_id != employee
                             or contract.state in ('close', 'cancel')):
                # Trainer changed, or the contract was already closed by a
                # retirement: never reuse it.
                contract = Contract
            if not contract:
                contract = Contract.search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ('draft', 'open')),
                    ('date_start', '<=', start),
                    '|', ('date_end', '=', False), ('date_end', '>=', start),
                ], limit=1)
            contract_vals = {
                'name': _('Trainer contract - %s') % employee.name,
                'employee_id': employee.id,
                'date_start': start,
                'date_end': rec.contract_end_date,
                'wage': rec.wage or 0.0,
            }
            # hr.contract requires a type; fall back to the first available
            # one when the version does not provide a default.
            if ('contract_type_id' in Contract._fields
                    and not Contract.default_get(
                        ['contract_type_id']).get('contract_type_id')):
                contract_type = self.env['hr.contract.type'].search(
                    [], limit=1)
                if contract_type:
                    contract_vals['contract_type_id'] = contract_type.id
            if contract:
                contract.write(contract_vals)
            else:
                contract = Contract.create(contract_vals)

            # A brand-new contract is created as *New*; an approved trainer
            # means the contract is in force, so run it.
            contract = rec._run_contract(contract)

            updates = {}
            if rec.employee_id != employee:
                updates['employee_id'] = employee.id
            if rec.contract_id != contract:
                updates['contract_id'] = contract.id
            if updates:
                rec.with_context(
                    umti_skip_trainer_sync=True).write(updates)
