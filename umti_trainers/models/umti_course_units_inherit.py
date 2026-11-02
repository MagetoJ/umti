from odoo import api, fields, models


class UmtiCourseUnitsInherit(models.Model):
    _inherit = 'umti.course.units'

    def write(self, vals):
        res = super().write(vals)
        watched = {'unit_level', 'unit_semester', 'active'}
        if watched & set(vals):
            courses = self.mapped('course_ids')
            if courses:
                self.env['umti.course']._refresh_for_courses(courses)
        return res
    allocation_ids = fields.Many2many(
        'umti.trainer.allocation', 'trainer_allocation_unit_rel',
        'unit_id', 'allocation_id',
        string='Trainers',
        help="Allocations through which this unit is taught.")

    unit_trainer_ids = fields.One2many(
        'umti.unit.trainer', 'unit_id', string='Unit Trainers',
        help="Trainer assignment per academic year and semester.")

    # TODO: refuse to archive a unit while students are still enrolled in it
    # (constraint on active). Archiving currently only blocks *new*
    # enrollments and trainer assignments; existing rows are left untouched.

    trainer_ids = fields.Many2many(
        'res.users', string='Trainers', compute='_compute_trainer_ids')

    trainer_count = fields.Integer(
        string='Trainers', compute='_compute_trainer_ids')

    @api.depends('unit_trainer_ids.trainer_id',
                 'unit_trainer_ids.trainer_id.user_id',
                 'unit_trainer_ids.active')
    def _compute_trainer_ids(self):
        # sudo: the unit form is readable by groups that have no access to
        # the assignments (e.g. students), and this field is display-only.
        for unit in self:
            assignments = unit.sudo().unit_trainer_ids.filtered('active')
            unit.trainer_ids = assignments.mapped('trainer_id.user_id')
            unit.trainer_count = len(unit.trainer_ids)
