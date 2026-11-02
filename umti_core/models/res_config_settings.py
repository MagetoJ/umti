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
        string="School Semester Structure",
        config_parameter='umti_core.school_term_structure', # This saves it perfectly to system parameters
        help="Select the structure of the school year.",
        default='two_sem'
    )
