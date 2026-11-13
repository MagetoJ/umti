# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class UmtiCourseLevel(models.Model):
    _name = 'umti.course.level'
    _description = 'Umti Course Level'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, index=True, tracking=True)
    term_pattern_id = fields.Many2one(
        'umti.term.pattern', string='Default Term Pattern', tracking=True,
        domain="[('active', '=', True)]",
        help="Pattern used by courses of this level unless the course sets "
             "its own. Empty means the company default from Settings.")
    effective_term_pattern_id = fields.Many2one(
        'umti.term.pattern', string='Effective Term Pattern',
        compute='_compute_effective_term_pattern_id',
        help="The pattern actually used: this level's pattern or the "
             "company default.")
    courses_counts = fields.Integer(string='Course Counts', compute='_compute_counts',)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


    @api.depends('term_pattern_id')
    def _compute_effective_term_pattern_id(self):
        default = self.env['umti.term.pattern']._default_pattern()
        for level in self:
            level.effective_term_pattern_id = (
                level.term_pattern_id or default)

    def _compute_counts(self):
          for rec in self:
            courses = self.env['umti.course'].search([('course_level_id','=',rec.id)])
            if courses:
                rec.courses_counts = len(courses)
            else:
                rec.courses_counts = 0

    def action_view_courses(self):
          return {
              'name': _('Courses'),
              'type': 'ir.actions.act_window',
              'view_type': 'form',
              'view_mode': 'list,form',
              'res_model': 'umti.course',
              'domain': [('course_level_id','=',self.id)],
              'context': self.env.context,
          }
    
    #prevent deleting a course level if it has courses
    @api.constrains('active')
    def _check_active(self):
        pass
