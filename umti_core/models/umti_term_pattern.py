from odoo import api, fields, models

#: Maps the legacy single ``school_term_structure`` setting onto its seeded
#: pattern, so existing installations keep their current calendar by default.
DEFAULT_PATTERN_BY_STRUCTURE = {
    'two_sem': 'umti_core.term_pattern_two_sem',
    'two_sem_qua': 'umti_core.term_pattern_two_sem_qua',
    'two_sem_final': 'umti_core.term_pattern_two_sem_final',
    'three_sem': 'umti_core.term_pattern_three_sem',
    'four_Quarter': 'umti_core.term_pattern_four_quarter',
    'others': 'umti_core.term_pattern_two_sem',
}


class UmtiTermPattern(models.Model):
    """How a course is divided into academic terms.

    A level sets the default pattern; a course may override it. Patterns are
    templates: the actual ``umti.academic.term`` records are generated from
    the pattern lines for a year or for an intake cohort.
    """

    _name = 'umti.term.pattern'
    _description = 'Term Pattern'
    _order = 'sequence, id'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection([
        ('semester', 'Semester'),
        ('trimester', 'Trimester'),
        ('quarter', 'Quarter'),
        ('module', 'Module'),
        ('block', 'Block'),
        ('continuous', 'Continuous'),
    ], default='semester', required=True, string='Term Label')
    scope = fields.Selection([
        ('per_year', 'Per academic year'),
        ('whole_course', 'Whole course'),
    ], default='per_year', required=True,
        help="Per academic year: the pattern repeats in every year of a "
             "multi-year course. Whole course: the pattern covers the entire "
             "course, as with a six-month block.")
    anchor = fields.Selection([
        ('academic_year', 'Academic year'),
        ('intake', 'Intake start'),
    ], default='academic_year', required=True,
        help="Where the generated term dates start from.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    line_ids = fields.One2many(
        'umti.term.pattern.line', 'pattern_id', string='Periods', copy=True)
    line_count = fields.Integer(compute='_compute_line_count')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'The pattern code must be unique per company.'),
    ]

    @api.depends('line_ids')
    def _compute_line_count(self):
        for pattern in self:
            pattern.line_count = len(pattern.line_ids)

    @api.model
    def _default_pattern(self):
        """The company-wide default pattern, from the legacy setting."""
        structure = self.env['ir.config_parameter'].sudo().get_param(
            'umti_core.school_term_structure', 'two_sem')
        xmlid = DEFAULT_PATTERN_BY_STRUCTURE.get(
            structure, 'umti_core.term_pattern_two_sem')
        return self.env.ref(xmlid, raise_if_not_found=False)

    def _main_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: not line.parent_sequence).sorted('sequence')

    def _child_lines(self, parent_sequence):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.parent_sequence == parent_sequence).sorted(
                'sequence')


class UmtiTermPatternLine(models.Model):
    _name = 'umti.term.pattern.line'
    _description = 'Term Pattern Period'
    _order = 'pattern_id, sequence, id'

    pattern_id = fields.Many2one(
        'umti.term.pattern', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, default=10)
    name = fields.Char(required=True)
    phase = fields.Selection([
        ('taught', 'Taught'),
        ('attachment', 'Attachment'),
        ('exam', 'Exam'),
    ], default='taught', required=True)
    duration_value = fields.Integer(
        default=0,
        help="Leave at 0 to split the available span equally with the other "
             "periods at the same level.")
    duration_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ], default='months', required=True)
    parent_sequence = fields.Integer(
        default=0,
        help="0 for a main period; otherwise the sequence of its parent.")
    is_subterm = fields.Boolean(compute='_compute_is_subterm', store=True)

    _sql_constraints = [
        ('pattern_sequence_uniq', 'unique(pattern_id, sequence)',
         'Each period sequence can appear only once per pattern.'),
    ]

    @api.depends('parent_sequence')
    def _compute_is_subterm(self):
        for line in self:
            line.is_subterm = bool(line.parent_sequence)
