from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# How many semesters a year of study holds, per term structure. One place: the
# ladder generator and the semester label both read it.
SEMESTERS_PER_YEAR = {
    'two_sem': 2,
    'two_sem_qua': 2,
    'two_sem_final': 2,
    'three_sem': 3,
    'four_Quarter': 4,
}
DEFAULT_SEMESTERS_PER_YEAR = 2


class UmtiStudentSemester(models.Model):
    _name = 'umti.student.semester'
    _description = 'Student Semester Lifecycle'
    _inherit = ['mail.thread']
    _order = 'student_id, sequence'

    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='cascade', index=True)
    course_year = fields.Integer(string="Year", readonly=True)
    course_id = fields.Many2one(
        'umti.course', string='Course',
        related='student_id.course_id', store=True, readonly=True)
    level_id = fields.Many2one(
       related='course_id.course_level_id', store=True, readonly=True)
       
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year',
        help="")
    academic_term_id = fields.Many2one(
        'umti.academic.term', string='Semester',
        domain="[('status', '=', 'in_progress')]",
        help="Only the semester currently in progress can be assigned.")
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Semester Label', store=True, compute='_compute_name')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('complete', 'Complete'),
    ], string='Status', default='draft', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)

    @api.model
    def _semesters_per_year(self):
        structure = self.env['ir.config_parameter'].sudo().get_param(
            'umti_core.school_term_structure', 'two_sem')
        return SEMESTERS_PER_YEAR.get(structure, DEFAULT_SEMESTERS_PER_YEAR)

    @api.depends('sequence')
    def _compute_name(self):
        per_year = self._semesters_per_year()
        for rec in self:
            index = max(rec.sequence or 1, 1) - 1
            rec.name = _("Year %(year)s Semester %(sem)s",
                         year=index // per_year + 1,
                         sem=index % per_year + 1)

    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Only semesters in 'Draft' state can be activated."))
            rec.write({'state': 'active'})

    def action_mark_complete(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_(
                    "Only active semesters can be marked complete."))
            if not rec.academic_term_id:
                raise UserError(_(
                    "Please assign an Semester before marking "
                    "this semester complete."))
            self._check_all_units_passed(rec)
            rec.write({'state': 'complete'})
            next_sem = self.search([
                ('student_id', '=', rec.student_id.id),
                ('state', '=', 'draft'),
            ], order='sequence', limit=1)
            if next_sem:
                next_sem.action_activate()

    def _results_state(self):
        """Result check for this semester, without raising.

        Returns a dict so callers can decide what to do:
          ok          every unit passed and finalised
          missing     nothing has been recorded for this semester yet
          failed      unit results marked as failed
          incomplete  unit results that are not finalised
        """
        self.ensure_one()
        empty = self.env['umti.unit.result']
        if 'umti.unit.result' not in self.env or not self.academic_term_id:
            # The exams module is not installed, or no semester is pinned to a
            # term: there is nothing to check, so do not block anything.
            return {'ok': True, 'missing': False, 'failed': empty,
                    'incomplete': empty}
        results = self.env['umti.unit.result'].search([
            ('student_id', '=', self.student_id.id),
            ('semester_id', '=', self.academic_term_id.id),
            ('course_id', '=', self.course_id.id),
        ])
        failed = results.filtered(lambda r: r.result == 'fail')
        incomplete = results.filtered(lambda r: not r.is_complete)
        return {
            'ok': bool(results) and not failed and not incomplete,
            'missing': not results,
            'failed': failed,
            'incomplete': incomplete,
        }

    def _check_all_units_passed(self, rec):
        state = rec._results_state()
        if state['missing']:
            raise ValidationError(_(
                "No unit results found for %(student)s in %(term)s. "
                "Cannot mark semester as complete without exam results.",
                student=rec.student_id.display_name,
                term=rec.academic_term_id.name,
            ))
        if state['failed']:
            raise ValidationError(_(
                "%(student)s has failed the following unit(s): %(units)s. "
                "All units must be passed before completing this semester.",
                student=rec.student_id.display_name,
                units=', '.join(state['failed'].mapped('unit_id.display_name')),
            ))
        if state['incomplete']:
            raise ValidationError(_(
                "%(student)s has incomplete results for: %(units)s. "
                "All unit results must be finalized before completing "
                "this semester.",
                student=rec.student_id.display_name,
                units=', '.join(
                    state['incomplete'].mapped('unit_id.display_name')),
            ))
