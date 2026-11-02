from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UmtiStudentUnitEnrollment(models.Model):
    _name = 'umti.student.unit.enrollment'
    _description = 'Student Unit Enrollment'
    _inherit = ['mail.thread']
    _rec_name = 'display_name'
    _order = 'academic_term_id, unit_id, student_id'

    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='cascade', index=True, tracking=True)
    course_id = fields.Many2one(
        'umti.course', string='Course', required=True, tracking=True)
    unit_id = fields.Many2one(
        'umti.course.units', string='Unit', required=True, tracking=True,
        domain="[('active', '=', True)]")
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester', tracking=True,
        domain="[('status', '=', 'in_progress')]")
    mapping_id = fields.Many2one(
        'umti.unit.trainer', string='Unit Trainer Assignment',
        compute='_compute_mapping_id', store=True, ondelete='set null',
        help="The department's trainer assignment for this unit and "
             "semester; the trainer is read from it.")
    trainer_id = fields.Many2one(
        'hr.employee', string='Trainer',
        related='mapping_id.trainer_id', store=True, readonly=True,
        help="Read from the unit trainer assignment: change it there to "
             "update every student at once.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('enrolled', 'Enrolled'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    ], default='draft', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    _sql_constraints = [
        ('student_unit_term_uniq',
         'UNIQUE(student_id, unit_id, academic_term_id)',
         'A student can only be enrolled in a unit once per semester.'),
    ]

    @api.depends('unit_id', 'academic_term_id')
    def _compute_mapping_id(self):
        """Point at the department's unit trainer assignment, if any."""
        Mapping = self.env['umti.unit.trainer'].sudo()
        unit_ids, term_ids = set(), set()
        for rec in self:
            if rec.unit_id and rec.academic_term_id:
                unit_ids.add(rec.unit_id.id)
                term_ids.add(rec.academic_term_id.id)
        found = {}
        if unit_ids and term_ids:
            mappings = Mapping.search([
                ('unit_id', 'in', list(unit_ids)),
                ('academic_term_id', 'in', list(term_ids)),
                ('active', '=', True),
            ])
            for mapping in mappings:
                found[(mapping.unit_id.id, mapping.academic_term_id.id)] = mapping
        for rec in self:
            rec.mapping_id = found.get(
                (rec.unit_id.id, rec.academic_term_id.id), Mapping)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s (%s)' % (
                rec.student_id.name or '',
                rec.unit_id.name or '',
                rec.academic_term_id.name or '')

    @api.constrains('unit_id')
    def _check_unit_active(self):
        for rec in self:
            if rec.unit_id and not rec.unit_id.active:
                raise ValidationError(_(
                    "Unit %(unit)s is archived: students cannot be enrolled "
                    "in it.", unit=rec.unit_id.name))
