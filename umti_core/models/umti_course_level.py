# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class UmtiCourseLevel(models.Model):
    _name = 'umti.course.level'
    _description = 'Umti Course Level'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, index=True, tracking=True)
    courses_counts = fields.Integer(string='Course Counts', compute='_compute_counts',)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.user.company_id)


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
