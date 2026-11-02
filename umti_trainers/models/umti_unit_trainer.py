from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UmtiUnitTrainer(models.Model):
    _name = 'umti.unit.trainer'
    _description = 'Unit Trainer Assignment'
    _inherit = ['mail.thread']
    _rec_name = 'display_name'
    _order = 'academic_year_id desc, academic_term_id, unit_id'

    unit_id = fields.Many2one(
        'umti.course.units', string='Unit', required=True,
        ondelete='cascade', index=True, tracking=True,
        domain="[('active', '=', True)]")
    unit_code = fields.Char(
        related='unit_id.code', store=True, string='Code')
    unit_type = fields.Selection(
        related='unit_id.unit_type', store=True, string='Type')
    credit_contribution = fields.Integer(
        related='unit_id.credit_contribution', store=True, string='Credits')
    department_id = fields.Many2one(
        related='unit_id.department_id', store=True, string='Department')
    trainer_id = fields.Many2one(
        'hr.employee', string='Trainer', required=True, tracking=True,
        domain="[('id', 'in', allowed_trainer_ids)]",
        help="Trainer taking the unit for this academic year and semester.")
    allowed_trainer_ids = fields.Many2many(
        'hr.employee', string='Available Trainers',
        compute='_compute_allowed_trainer_ids',
        help="Approved trainers the department allocated to this unit.")
    trainer_user_id = fields.Many2one(
        related='trainer_id.user_id', string='Trainer User', store=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True,
        tracking=True)
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True,
        tracking=True,
        domain="[('academic_year_id', '=', academic_year_id),"
               " ('status', '=', 'in_progress')]")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    student_count = fields.Integer(
        string='Students', compute='_compute_student_count')

    def _compute_student_count(self):
        """Students enrolled in this unit for this term (one batched query)."""
        Enrollment = self.env['umti.student.unit.enrollment'].sudo()
        counts = {}
        if self.ids:
            enrollments = Enrollment.search([
                ('unit_id', 'in', self.unit_id.ids),
                ('academic_term_id', 'in', self.academic_term_id.ids),
                ('state', '=', 'enrolled'),
            ])
            for enrollment in enrollments:
                key = (enrollment.unit_id.id,
                       enrollment.academic_term_id.id)
                counts[key] = counts.get(key, 0) + 1
        for rec in self:
            rec.student_count = counts.get(
                (rec.unit_id.id, rec.academic_term_id.id), 0)

    def action_view_students(self):
        """Open the students enrolled in this unit for this semester."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Students - %s', self.display_name),
            'res_model': 'umti.student.unit.enrollment',
            'view_mode': 'list,form',
            'domain': [
                ('unit_id', '=', self.unit_id.id),
                ('academic_term_id', '=', self.academic_term_id.id),
                ('state', '=', 'enrolled'),
            ],
            'context': {'create': False, 'search_default_group_student': 1},
        }

    _sql_constraints = [
        ('unit_term_uniq',
         'UNIQUE(unit_id, academic_term_id)',
         'A unit can only have one trainer per semester.'),
    ]

    @api.depends('unit_id', 'trainer_id.name', 'academic_term_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s (%s)' % (
                rec.unit_id.name or '',
                rec.trainer_id.name or _('No Trainer'),
                rec.academic_term_id.name or '')

    @api.depends('unit_id')
    def _compute_allowed_trainer_ids(self):
        """Approved, active trainer allocations of the unit."""
        Allocation = self.env['umti.trainer.allocation'].sudo()
        Employee = self.env['hr.employee']
        unit_ids = self.mapped('unit_id').ids
        by_unit = {}
        if unit_ids:
            allocations = Allocation.search([
                ('unit_ids', 'in', unit_ids),
                ('active', '=', True),
                ('state', '=', 'approved'),
            ])
            for allocation in allocations:
                for unit in allocation.unit_ids:
                    if unit.id in unit_ids:
                        by_unit.setdefault(unit.id, Employee)
                        by_unit[unit.id] |= allocation.employee_id
        for rec in self:
            rec.allowed_trainer_ids = by_unit.get(rec.unit_id.id, Employee)

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        """Default to the first trainer allocated to the unit."""
        if self.trainer_id not in self.allowed_trainer_ids:
            self.trainer_id = self.allowed_trainer_ids[:1]

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        if (self.academic_term_id
                and self.academic_term_id.academic_year_id
                != self.academic_year_id):
            self.academic_term_id = False

    @api.onchange('academic_term_id')
    def _onchange_academic_term_id(self):
        if self.academic_term_id:
            self.academic_year_id = self.academic_term_id.academic_year_id

    @api.constrains('academic_year_id', 'academic_term_id')
    def _check_term_year(self):
        for rec in self:
            if (rec.academic_term_id
                    and rec.academic_term_id.academic_year_id
                    != rec.academic_year_id):
                raise ValidationError(_(
                    "Semester %(term)s does not belong to academic year "
                    "%(year)s.",
                    term=rec.academic_term_id.name,
                    year=rec.academic_year_id.name))

    @api.constrains('unit_id')
    def _check_unit_active(self):
        for rec in self:
            if rec.unit_id and not rec.unit_id.active:
                raise ValidationError(_(
                    "Unit %(unit)s is archived: no trainer can be assigned "
                    "to it.", unit=rec.unit_id.name))

    @api.constrains('unit_id', 'trainer_id')
    def _check_trainer_allocated(self):
        if self.env.context.get('skip_trainer_allocation_check'):
            return
        for rec in self:
            if rec.trainer_id and rec.trainer_id not in rec.allowed_trainer_ids:
                raise ValidationError(_(
                    "%(trainer)s is not allocated to unit %(unit)s. Approve "
                    "a trainer allocation for the unit first.",
                    trainer=rec.trainer_id.name,
                    unit=rec.unit_id.name))
