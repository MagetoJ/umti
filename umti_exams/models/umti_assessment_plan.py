from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .assessment_types import (
    ASSESSMENT_TYPES, CORE_TYPES, DEFAULT_CORE_WEIGHTS, OPTIONAL_TYPES)

MANAGER_GROUPS = ('umti_exams.group_umti_exams_manager', 'base.group_system')
HOD_GROUP = 'umti_exams.group_umti_exams_hod'


class UmtiAssessmentPlan(models.Model):
    """What assessments run in a department during a semester.

    CAT, Assignment and Final Exam are always part of the plan and are the
    only types that compute to the final unit mark (their weights total 100).
    Every other type can be enabled by the Head of Department, but is
    recorded only.
    """
    _name = 'umti.assessment.plan'
    _description = 'Department Assessment Plan'
    _inherit = ['mail.thread']
    _order = 'semester_id desc, department_id'

    name = fields.Char(compute='_compute_name', store=True)
    semester_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True,
        ondelete='cascade', index=True, tracking=True)
    academic_year_id = fields.Many2one(
        related='semester_id.academic_year_id', store=True, string='Academic Year')
    department_id = fields.Many2one(
        'umti.department', string='Department', required=True,
        ondelete='cascade', index=True, tracking=True)
    hod_id = fields.Many2one(
        related='department_id.manager_id', string='Head of Department')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed')],
        default='draft', required=True, copy=False, tracking=True)
    line_ids = fields.One2many(
        'umti.assessment.plan.line', 'plan_id', string='Assessment Types',
        default=lambda self: self._default_line_commands())
    core_weight_total = fields.Float(
        string='Final Mark Weight Total (%)', compute='_compute_core_weight_total')

    _sql_constraints = [
        ('semester_department_uniq', 'unique(semester_id, department_id)',
         'A department can only have one assessment plan per semester.'),
    ]

    # ------------------------------------------------------------ defaults
    @api.model
    def _default_line_commands(self):
        commands = []
        for code, _label in ASSESSMENT_TYPES:
            core = code in CORE_TYPES
            commands.append((0, 0, {
                'assessment_type': code,
                'enabled': core,
                'weight': DEFAULT_CORE_WEIGHTS.get(code, 0.0) if core else 0.0,
            }))
        return commands

    @api.depends('semester_id.name', 'department_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = "%s - %s" % (
                rec.department_id.name or '', rec.semester_id.name or '')

    @api.depends('line_ids.weight', 'line_ids.assessment_type')
    def _compute_core_weight_total(self):
        for rec in self:
            rec.core_weight_total = sum(
                rec.line_ids.filtered('is_core').mapped('weight'))

    # ------------------------------------------------------------- helpers
    @api.model
    def _get_or_create(self, semester, department):
        """Return the plan for (semester, department), creating the default one."""
        plan = self.sudo().search([
            ('semester_id', '=', semester.id),
            ('department_id', '=', department.id)], limit=1)
        if not plan:
            plan = self.sudo().with_context(tracking_disable=True).create({
                'semester_id': semester.id,
                'department_id': department.id,
                'company_id': (department.company_id or self.env.company).id,
            })
        return plan

    def core_weights(self):
        """{'cat': 20.0, 'assignment': 10.0, 'final': 70.0}"""
        self.ensure_one()
        weights = dict(DEFAULT_CORE_WEIGHTS)
        for line in self.line_ids.filtered('is_core'):
            weights[line.assessment_type] = line.weight
        return weights

    def enabled_types(self):
        """Set of assessment types that may be created under this plan."""
        self.ensure_one()
        return set(CORE_TYPES) | set(
            self.line_ids.filtered('enabled').mapped('assessment_type'))

    def _check_editor(self):
        """Managers, or the HOD of the plan's own department, may change a plan."""
        if self.env.su:
            return
        user = self.env.user
        if any(user.has_group(g) for g in MANAGER_GROUPS):
            return
        for plan in self:
            dept = plan.sudo().department_id
            if not (user.has_group(HOD_GROUP) and dept.manager_id == user):
                raise AccessError(_(
                    "Only the Head of Department of %s or an exams manager can "
                    "change this assessment plan.", dept.display_name))

    def _check_manager(self):
        if not self.env.su and not any(
                self.env.user.has_group(g) for g in MANAGER_GROUPS):
            raise AccessError(_("Only an exams manager can perform this action."))

    def _refresh_results(self):
        """Recompute the unit results affected by a change of this plan."""
        Assessment = self.env['umti.assessment'].sudo()
        Result = self.env['umti.unit.result'].sudo()
        for plan in self:
            assessments = Assessment.search([
                ('semester_id', '=', plan.semester_id.id),
                ('department_id', '=', plan.department_id.id),
                ('state', '!=', 'cancelled')])
            keys = assessments.mark_ids._result_keys()
            results = Result.search([
                ('semester_id', '=', plan.semester_id.id),
                ('unit_id', 'in', assessments.unit_id.ids),
                ('course_id.department_id', '=', plan.department_id.id)])
            keys |= {(r.student_id.id, r.unit_id.id, r.semester_id.id,
                      r.academic_year_id.id) for r in results}
            Result._refresh(keys)

    # ----------------------------------------------------------------- ORM
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_editor()
        records.line_ids._check_plan_totals()
        return records

    def write(self, vals):
        self._check_editor()
        if set(vals) - {'state'} and any(r.state == 'confirmed' for r in self):
            raise UserError(_(
                "This assessment plan is confirmed and locked. Ask an exams "
                "manager to reset it to draft before changing it."))
        # Line commands are written one by one, so totals are validated (and
        # results recomputed) once, after every change of this save is applied.
        res = super(UmtiAssessmentPlan, self.with_context(plan_writing=True)).write(vals)
        if 'line_ids' in vals:
            self.line_ids._check_plan_totals()
            self._refresh_results()
        return res

    # ------------------------------------------------------------- actions
    def action_confirm(self):
        self._check_editor()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft plans can be confirmed."))
            rec.line_ids._check_plan_totals()
        self.write({'state': 'confirmed'})

    def action_reset_draft(self):
        self._check_manager()
        if any(rec.state != 'confirmed' for rec in self):
            raise UserError(_("Only confirmed plans can be reset to draft."))
        self.write({'state': 'draft'})


class UmtiAssessmentPlanLine(models.Model):
    _name = 'umti.assessment.plan.line'
    _description = 'Department Assessment Plan Line'
    _order = 'plan_id, id'

    plan_id = fields.Many2one(
        'umti.assessment.plan', required=True, ondelete='cascade', index=True)
    assessment_type = fields.Selection(ASSESSMENT_TYPES, string='Type', required=True)
    is_core = fields.Boolean(
        string='Counts to Final Mark', compute='_compute_is_core', store=True)
    enabled = fields.Boolean(string='Enabled', default=False)
    weight = fields.Float(
        string='Weight (%)',
        help="Share of the final unit mark. Only CAT, Assignment and Final Exam "
             "carry a weight; their weights must total 100.")
    state = fields.Selection(related='plan_id.state')

    _sql_constraints = [
        ('plan_type_uniq', 'unique(plan_id, assessment_type)',
         'Each assessment type can appear only once per plan.'),
    ]

    @api.depends('assessment_type')
    def _compute_is_core(self):
        for line in self:
            line.is_core = line.assessment_type in CORE_TYPES

    @api.constrains('assessment_type', 'enabled', 'weight')
    def _check_line(self):
        for line in self:
            if line.is_core and not line.enabled:
                raise ValidationError(_(
                    "%s is a core assessment and cannot be disabled.",
                    dict(ASSESSMENT_TYPES)[line.assessment_type]))
            if line.is_core and not (0.0 <= line.weight <= 100.0):
                raise ValidationError(_("A weight must be between 0 and 100."))
            if not line.is_core and line.weight:
                raise ValidationError(_(
                    "%s does not count to the final mark, so it cannot have a weight.",
                    dict(ASSESSMENT_TYPES)[line.assessment_type]))
            if not line.is_core and not line.enabled:
                used = self.env['umti.assessment'].sudo().search_count([
                    ('semester_id', '=', line.plan_id.semester_id.id),
                    ('department_id', '=', line.plan_id.department_id.id),
                    ('assessment_type', '=', line.assessment_type),
                    ('state', '!=', 'cancelled')])
                if used:
                    raise ValidationError(_(
                        "%(type)s cannot be disabled: %(count)s assessment(s) of this "
                        "type already exist in this semester.",
                        type=dict(ASSESSMENT_TYPES)[line.assessment_type], count=used))

    def _check_plan_totals(self):
        for plan in self.plan_id:
            core = plan.line_ids.filtered('is_core')
            if len(core) == len(CORE_TYPES) and abs(sum(core.mapped('weight')) - 100.0) > 0.01:
                raise ValidationError(_(
                    "CAT, Assignment and Final Exam weights must total 100%% "
                    "(currently %.2f%%).", sum(core.mapped('weight'))))

    @api.model_create_multi
    def create(self, vals_list):
        plans = self.env['umti.assessment.plan'].browse(
            [v['plan_id'] for v in vals_list if v.get('plan_id')])
        if any(p.state == 'confirmed' for p in plans):
            raise UserError(_("This assessment plan is confirmed and locked."))
        return super().create(vals_list)

    def write(self, vals):
        self.plan_id._check_editor()
        if any(p.state == 'confirmed' for p in self.plan_id):
            raise UserError(_(
                "This assessment plan is confirmed and locked. Ask an exams "
                "manager to reset it to draft before changing it."))
        res = super().write(vals)
        if {'weight', 'enabled'} & set(vals) and not self.env.context.get('plan_writing'):
            self._check_plan_totals()      # edited directly, not through the plan form
            self.plan_id._refresh_results()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_core(self):
        if self.filtered('is_core') and not self.env.context.get('force_delete_plan'):
            raise UserError(_("Core assessment lines cannot be deleted."))
