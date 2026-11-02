from odoo import fields, models


class UmtiDepartmentInherit(models.Model):
    _inherit = 'umti.department'

    manager_id = fields.Many2one(
        'res.users', string='Head of Department',
        domain="[('share', '=', False)]", tracking=True)

    student_count = fields.Integer(
        compute='_compute_student_count', string='Students')
    course_count = fields.Integer(
        compute='_compute_course_count', string='Courses')
    trainer_count = fields.Integer(
        compute='_compute_trainer_count', string='Trainers')
    trainer_ids = fields.Many2many(
        'res.users', 'dept_trainer_computed_rel', 'dept_id', 'user_id',
        compute='_compute_trainer_ids', string='Allocated Trainers')
    trainer_allocation_ids = fields.One2many(
        'umti.trainer.allocation', 'department_id',
        string='Trainer Allocations')

    exam_pass_rate = fields.Float(
        compute='_compute_exam_metrics', string='Pass Rate (%)', digits=(5, 2))
    avg_exam_mark = fields.Float(
        compute='_compute_exam_metrics', string='Avg Exam Mark (%)', digits=(5, 2))
    unit_result_ids = fields.Many2many(
        'umti.unit.result', 'dept_unit_result_computed_rel', 'dept_id', 'result_id',
        compute='_compute_unit_result_ids', string='Unit Results')
    course_ids = fields.Many2many(
        'umti.course', 'dept_course_computed_rel', 'dept_id', 'course_id',
        compute='_compute_course_ids', string='Courses')    

    def _compute_student_count(self):
        Student = self.env['school.student']
        for dept in self:
            dept.student_count = Student.search_count([
                ('department_id', '=', dept.id),
                ('state', '=', 'active'),
            ])

    def _compute_course_count(self):
        for dept in self:
            dept.course_count = len(dept.course_ids.filtered('active'))

    def _compute_trainer_count(self):
        Allocation = self.env['umti.trainer.allocation']
        for dept in self:
            allocations = Allocation.search([
                ('department_id', '=', dept.id),
                ('state', '=', 'approved'),
            ])
            dept.trainer_count = len(
                allocations.mapped('employee_id.user_id'))

    def _compute_trainer_ids(self):
        Allocation = self.env['umti.trainer.allocation']
        for dept in self:
            allocations = Allocation.search([
                ('department_id', '=', dept.id),
                ('state', '=', 'approved'),
            ])
            dept.trainer_ids = allocations.mapped('employee_id.user_id')

    def _compute_course_ids(self):
        Course = self.env['umti.course'].sudo()
        for dept in self:
            dept.course_ids = Course.search([
                ('department_id', '=', dept.id),
                ('active', '=', True),
            ])

    def _compute_exam_metrics(self):
        """Pass rate and average mark over published assessment marks.

        Three aggregates per department, computed in the database. Loading
        every mark to count them in Python made opening one department cost a
        full table read once a department had a few thousand marks.

        Guarded so a deployment without ``umti_exams`` still loads the
        department form.
        """
        Mark = (self.env['umti.assessment.mark']
                if 'umti.assessment.mark' in self.env else None)
        for dept in self:
            dept.exam_pass_rate = 0.0
            dept.avg_exam_mark = 0.0
            if Mark is None:
                continue
            domain = [('unit_id.department_id', '=', dept.id),
                      ('state', '=', 'published')]
            total = Mark.search_count(domain)
            if not total:
                continue
            passed = Mark.search_count(domain + [('percentage', '>=', 40)])
            average = Mark._read_group(domain, aggregates=['percentage:avg'])
            dept.exam_pass_rate = (passed / total) * 100
            dept.avg_exam_mark = (average[0][0] or 0.0) if average else 0.0

    def _compute_unit_result_ids(self):
        Result = (self.env['umti.unit.result']
                  if 'umti.unit.result' in self.env else None)
        for dept in self:
            dept.unit_result_ids = Result.search([
                ('unit_id.department_id', '=', dept.id),
            ]) if Result is not None else False

    def action_view_students(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Department Students',
            'res_model': 'school.student',
            'view_mode': 'list,form',
            'domain': [('department_id', '=', self.id)],
        }

    def action_view_courses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Department Courses',
            'res_model': 'umti.course',
            'view_mode': 'list,form',
            'domain': [('department_id', '=', self.id)],
        }

    def action_view_trainers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Department Trainers',
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.trainer_ids.ids)],
        }

    def action_view_exam_marks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Department Unit Results',
            'res_model': 'umti.unit.result',
            'view_mode': 'list,pivot,graph',
            'domain': [('course_id.department_id', '=', self.id)],
        }