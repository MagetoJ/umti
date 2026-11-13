from odoo import _, fields, models


class UmtiSlotGeneratorWizard(models.TransientModel):
    """Thin shortcut: pick a template and generate its slots.

    Times and days are no longer typed here; they live on the template so
    they can be reused.
    """
    _name = 'umti.slot.generator.wizard'
    _description = 'Generate Time Slots from a Template'

    template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Slot Template', required=True,
        domain="[('active', '=', True)]")

    def action_generate_slots(self):
        self.ensure_one()
        self.template_id.action_apply()
        return self.template_id.action_view_slots()
