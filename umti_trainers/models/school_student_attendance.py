from odoo import _, api, fields, models

DEFAULT_ATTENDANCE_THRESHOLD = 75.0


class SchoolStudentAttendance(models.Model):
    """Attendance figures on the student.

    Everything here is computed from submitted attendance sheets, so it can
    be moved into ``umti_students`` unchanged when the modules are merged.
    """
    _inherit = 'school.student'

    attendance_line_ids = fields.One2many(
        'umti.attendance.line', 'student_id', string='Attendance Lines')
    attendance_submitted_line_ids = fields.One2many(
        'umti.attendance.line', 'student_id', string='Attendance Records',
        domain=[('sheet_state', '=', 'done')])
    attendance_summary_ids = fields.One2many(
        'umti.attendance.summary', 'student_id', string='Attendance by Unit')

    attendance_session_count = fields.Integer(
        string='Sessions', compute='_compute_attendance_stats', store=True)
    attendance_present_count = fields.Integer(
        string='Present', compute='_compute_attendance_stats', store=True)
    attendance_absent_count = fields.Integer(
        string='Absent', compute='_compute_attendance_stats', store=True)
    attendance_excused_count = fields.Integer(
        string='Excused', compute='_compute_attendance_stats', store=True)
    attendance_rate = fields.Float(
        string='Attendance %', compute='_compute_attendance_stats',
        store=True, digits=(5, 1),
        help="Present / (Present + Absent) over submitted sheets. "
             "Excused sessions are ignored.")
    attendance_at_risk = fields.Boolean(
        string='Low Attendance', compute='_compute_attendance_state',
        search='_search_attendance_at_risk')
    attendance_state = fields.Selection(
        [('no_data', 'No Data'), ('good', 'Good'), ('at_risk', 'Below Threshold')],
        string='Attendance Status', compute='_compute_attendance_state')

    @api.model
    def _attendance_threshold(self):
        """Minimum attendance % (system parameter ``umti_trainers.attendance_threshold``)."""
        value = self.env['ir.config_parameter'].sudo().get_param(
            'umti_trainers.attendance_threshold')
        try:
            return float(value)
        except (TypeError, ValueError):
            return DEFAULT_ATTENDANCE_THRESHOLD

    @api.depends(
        'attendance_line_ids.sheet_state',
        'attendance_line_ids.is_present',
        'attendance_line_ids.counts_in_rate')
    def _compute_attendance_stats(self):
        for student in self:
            lines = student.attendance_line_ids.filtered(
                lambda l: l.sheet_state == 'done')
            present = len(lines.filtered('is_present'))
            absent = len(lines.filtered(
                lambda l: not l.is_present and l.counts_in_rate))
            counted = present + absent
            student.attendance_session_count = len(lines)
            student.attendance_present_count = present
            student.attendance_absent_count = absent
            student.attendance_excused_count = len(lines) - counted
            student.attendance_rate = (
                round(present * 100.0 / counted, 1) if counted else 0.0)

    @api.depends('attendance_rate', 'attendance_present_count', 'attendance_absent_count')
    def _compute_attendance_state(self):
        threshold = self._attendance_threshold()
        for student in self:
            counted = student.attendance_present_count + student.attendance_absent_count
            if not counted:
                student.attendance_state = 'no_data'
            elif student.attendance_rate < threshold:
                student.attendance_state = 'at_risk'
            else:
                student.attendance_state = 'good'
            student.attendance_at_risk = student.attendance_state == 'at_risk'

    def _search_attendance_at_risk(self, operator, value):
        threshold = self._attendance_threshold()
        positive = (operator == '=') == bool(value)
        if positive:
            return [
                '&', ('attendance_rate', '<', threshold),
                '|', ('attendance_present_count', '>', 0),
                ('attendance_absent_count', '>', 0),
            ]
        return [
            '|', ('attendance_rate', '>=', threshold),
            '&', ('attendance_present_count', '=', 0),
            ('attendance_absent_count', '=', 0),
        ]

    # ------------------------------------------------------------------
    # Actions and the hook the students module / portal can call
    # ------------------------------------------------------------------
    def action_view_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance - %s', self.name),
            'res_model': 'umti.attendance.line',
            'view_mode': 'list,pivot',
            'domain': [('student_id', '=', self.id), ('sheet_state', '=', 'done')],
            'context': {'default_student_id': self.id, 'create': False},
        }

    def _get_attendance_summary(self):
        """Plain-dict attendance data for one student (portal, reports, merge)."""
        self.ensure_one()
        return {
            'sessions': self.attendance_session_count,
            'present': self.attendance_present_count,
            'absent': self.attendance_absent_count,
            'excused': self.attendance_excused_count,
            'rate': self.attendance_rate,
            'state': self.attendance_state,
            'threshold': self._attendance_threshold(),
            'units': [{
                'unit': s.unit_id.display_name,
                'term': s.academic_term_id.display_name,
                'sessions': s.session_count,
                'present': s.present_count,
                'absent': s.absent_count,
                'excused': s.excused_count,
                'rate': s.attendance_rate,
                'last_session': s.last_session_date,
            } for s in self.attendance_summary_ids],
        }
