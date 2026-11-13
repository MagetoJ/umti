from odoo import fields, models


class UmtiCourseUnitLine(models.Model):
    """Placement of a unit inside one course's term pattern.

    The unit itself is a catalogue record and can be shared by many courses;
    this table says in which year and period each course teaches it.
    ``period_sequence`` matches a ``umti.term.pattern.line`` sequence.
    """

    _name = 'umti.course.unit.line'
    _description = 'Course Unit Placement'
    _order = 'course_id, course_year, period_sequence, id'
    _rec_name = 'unit_id'

    course_id = fields.Many2one(
        'umti.course', required=True, ondelete='cascade', index=True)
    unit_id = fields.Many2one(
        'umti.course.units', required=True, ondelete='cascade', index=True)
    course_year = fields.Integer(
        default=1, required=True,
        help="Study year this placement belongs to, starting at 1.")
    period_sequence = fields.Integer(
        default=10, required=True,
        help="Sequence of the pattern line (term) that teaches this unit.")
    phase = fields.Selection([
        ('taught', 'Taught'),
        ('attachment', 'Attachment'),
        ('exam', 'Exam'),
    ], default='taught', required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('course_unit_period_uniq',
         'unique(course_id, unit_id, course_year, period_sequence)',
         'A unit can appear only once per course, year and period.'),
    ]
