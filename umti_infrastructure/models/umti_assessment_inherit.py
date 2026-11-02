from odoo import fields, models


class UmtiAssessment(models.Model):
    _inherit = 'umti.assessment'

    facility_id = fields.Many2one(
        'umti.facility', string='Exam Venue',
        domain="[('status', '!=', 'decommissioned')]", tracking=True)

    def _has_venue(self):
        self.ensure_one()
        return bool(self.facility_id)


class UmtiAssessmentUnitSchedule(models.Model):
    _inherit = 'umti.assessment.unit.schedule'

    facility_id = fields.Many2one(
        'umti.facility', string='Venue', domain="[('status', '!=', 'decommissioned')]")
