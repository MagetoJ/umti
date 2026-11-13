from odoo import _, models


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    def _new_area_record(self, model, name, context=None):
        self.ensure_one()
        vals = dict(context or {}, default_student_id=self.id)
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': vals,
            'target': 'current',
        }

    def _view_area(self, model, title, list_view):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': model,
            'view_mode': 'list,form',
            'views': [(self.env.ref(list_view).id, 'list'), (False, 'form')],
            'domain': [('student_id', '=', self.id)],
        }
