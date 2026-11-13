from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    school_term_structure = fields.Selection(
       [('two_sem', 'Two Semesters'),
         ('two_sem_qua', 'Two Semesters subdivided by Quarters'),
         ('two_sem_final', 'Two Semesters subdivided by Quarters and Final Exams'),
         ('three_sem', 'Three Trimesters'),
         ('four_Quarter', 'Four Quarters'),
         ('others', 'Other (overlapping semesters, custom schedules)')],
        string="Default Term Pattern",
        config_parameter='umti_core.school_term_structure',
        help="Fallback pattern when neither the course nor its level sets "
             "one. Seeded term patterns mirror these options.",
        default='two_sem'
    )
