from odoo import fields, models

HELP = ("Time structure used by terms of this record. The most specific one "
        "wins: term, then course, then level, then term pattern.")


class UmtiCourseLevelSlotTemplate(models.Model):
    _inherit = 'umti.course.level'

    slot_template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Slot Template', help=HELP)


class UmtiCourseSlotTemplate(models.Model):
    _inherit = 'umti.course'

    slot_template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Slot Template', help=HELP)


class UmtiTermPatternSlotTemplate(models.Model):
    _inherit = 'umti.term.pattern'

    slot_template_id = fields.Many2one(
        'umti.timetable.slot.template', string='Slot Template', help=HELP)
