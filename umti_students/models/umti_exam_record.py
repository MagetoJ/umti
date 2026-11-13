# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UmtiExamRecord(models.Model):
    _name = 'umti.exam.record'
    _description = 'Umti Student Exam Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'exam_date desc, id desc'

    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='cascade', index=True, tracking=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True, tracking=True)
    semester_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True, tracking=True,
        domain="[('academic_year_id', '=', academic_year_id)]")
    course_id = fields.Many2one(
        'umti.course', string='Course', required=True, tracking=True)
    # helper so the unit dropdown only offers units that belong to the course
    course_unit_ids = fields.Many2many(
        'umti.course.units', related='course_id.unit_ids', string='Course Units')
    unit_id = fields.Many2one(
        'umti.course.units', string='Unit', required=True, tracking=True,
        domain="[('id', 'in', course_unit_ids)]")
    unit_code = fields.Char(related='unit_id.code', string='Unit Code', store=True)
    unit_credit = fields.Integer(
        related='unit_id.credit_contribution', string='Credits', store=True)

    exam_date = fields.Date(tracking=True)
    marks = fields.Float(tracking=True)
    max_marks = fields.Float(default=100.0)
    percentage = fields.Float(compute='_compute_result', store=True)
    grade = fields.Char(compute='_compute_result', store=True)
    result = fields.Selection(
        [('pass', 'Pass'), ('fail', 'Fail')], compute='_compute_result', store=True)
    remarks = fields.Char()

    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.user.company_id)

    @api.depends('student_id', 'unit_id', 'academic_year_id')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.student_id.display_name, rec.unit_id.name, rec.academic_year_id.name]
            rec.display_name = ' / '.join(p for p in parts if p) or _('New Exam Record')

    @api.depends('marks', 'max_marks')
    def _compute_result(self):
        for rec in self:
            pct = (rec.marks / rec.max_marks * 100.0) if rec.max_marks else 0.0
            rec.percentage = pct
            if pct >= 70:
                rec.grade = 'A'
            elif pct >= 60:
                rec.grade = 'B'
            elif pct >= 50:
                rec.grade = 'C'
            elif pct >= 40:
                rec.grade = 'D'
            else:
                rec.grade = 'F'
            rec.result = 'pass' if pct >= 40 else 'fail'

    @api.onchange('student_id')
    def _onchange_student_id(self):
        if self.student_id:
            self.course_id = self.student_id.course_id

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.unit_id and self.unit_id not in self.course_id.unit_ids:
            self.unit_id = False

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        if self.semester_id and self.semester_id.academic_year_id != self.academic_year_id:
            self.semester_id = False

    @api.constrains('marks', 'max_marks')
    def _check_marks(self):
        for rec in self:
            if rec.marks < 0 or rec.marks > rec.max_marks:
                raise ValidationError(_("Marks must be between 0 and the maximum marks."))

    @api.constrains('academic_year_id', 'semester_id')
    def _check_semester_in_year(self):
        for rec in self:
            if rec.semester_id and rec.semester_id.academic_year_id != rec.academic_year_id:
                raise ValidationError(_("The semester does not belong to the selected academic year."))
