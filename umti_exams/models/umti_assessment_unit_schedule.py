from odoo import api, fields, models


class UmtiAssessmentUnitSchedule(models.Model):
    _name = 'umti.assessment.unit.schedule'
    _description = 'Unit Assessment Schedule'

    assessment_id = fields.Many2one('umti.assessment', string='Assessment', required=True, ondelete='cascade')
    unit_id = fields.Many2one('umti.course.units', string='Course Unit', required=True)
    date = fields.Date(string='Exam Date')
    
    # Timing & Duration (Default 2.0 Hours, editable float)
    start_time = fields.Float(string='Start Time', default=8.0)
    duration = fields.Float(string='Duration (Hours)', default=2.0, help="Default is 2 hours. Editable for multi-hour or multi-day assessments.")
    end_time = fields.Float(string='End Time', compute='_compute_end_time', store=True, readonly=False)
    
    @api.depends('start_time', 'duration')
    def _compute_end_time(self):
        for rec in self:
            if rec.start_time is not False and rec.duration is not False:
                rec.end_time = rec.start_time + rec.duration