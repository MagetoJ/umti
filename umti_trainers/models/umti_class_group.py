from odoo import api, fields, models


class UmtiClassGroup(models.Model):
    """A teaching group that can span several courses and cohorts.

    Shared units are taught once to students whose academic terms differ.
    The group holds the terms whose students attend together; attendance
    rosters and timetables point at the group instead of one term.
    """

    _name = 'umti.class.group'
    _description = 'Shared Teaching Group'
    _order = 'unit_id, name'

    name = fields.Char(required=True, tracking=True)
    unit_id = fields.Many2one(
        'umti.course.units', string='Unit', required=True,
        ondelete='restrict', tracking=True,
        domain="[('active', '=', True)]")
    term_ids = fields.Many2many(
        'umti.academic.term', 'umti_class_group_term_rel',
        'group_id', 'term_id', string='Cohort Terms',
        help="Terms whose students attend this group together.")
    course_ids = fields.Many2many(
        'umti.course', string='Courses', compute='_compute_course_ids',
        store=True)
    department_id = fields.Many2one(
        related='unit_id.department_id', store=True, string='Department')
    enrollment_count = fields.Integer(
        string='Enrollments', compute='_compute_enrollment_count')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    @api.depends('term_ids', 'term_ids.course_id')
    def _compute_course_ids(self):
        for group in self:
            group.course_ids = group.term_ids.mapped('course_id')

    @api.depends('unit_id', 'term_ids')
    def _compute_enrollment_count(self):
        Enrollment = self.env['umti.student.unit.enrollment']
        for group in self:
            group.enrollment_count = len(group._get_enrollments())

    def _get_enrollments(self):
        self.ensure_one()
        if not (self.unit_id and self.term_ids):
            return self.env['umti.student.unit.enrollment']
        return self.env['umti.student.unit.enrollment'].search([
            ('unit_id', '=', self.unit_id.id),
            ('academic_term_id', 'in', self.term_ids.ids),
            ('state', '=', 'enrolled'),
        ])

    def action_view_enrollments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Group Enrollments',
            'res_model': 'umti.student.unit.enrollment',
            'view_mode': 'list,form',
            'domain': [
                ('unit_id', '=', self.unit_id.id),
                ('academic_term_id', 'in', self.term_ids.ids),
                ('state', '=', 'enrolled'),
            ],
        }
