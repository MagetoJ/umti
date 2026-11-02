from odoo import fields, models, tools


class UmtiAttendanceSummary(models.Model):
    """Read-only per student / unit / term attendance figures.

    Built only from *submitted* sheets. Excused absences (status with
    ``counts_in_rate`` unticked) are reported separately and left out of
    the percentage.
    """
    _name = 'umti.attendance.summary'
    _description = 'Attendance Summary'
    _auto = False
    _order = 'student_id, academic_term_id, unit_id'

    student_id = fields.Many2one('school.student', string='Student', readonly=True)
    course_id = fields.Many2one('umti.course', string='Course', readonly=True)
    department_id = fields.Many2one('umti.department', string='Department', readonly=True)
    unit_id = fields.Many2one('umti.course.units', string='Unit', readonly=True)
    academic_term_id = fields.Many2one('umti.academic.term', string='Semester', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    session_count = fields.Integer(string='Sessions', readonly=True)
    present_count = fields.Integer(string='Present', readonly=True)
    absent_count = fields.Integer(string='Absent', readonly=True)
    excused_count = fields.Integer(string='Excused', readonly=True)
    attendance_rate = fields.Float(
        string='Attendance %', readonly=True, aggregator='avg',
        help="Present / (Present + Absent). Excused sessions are ignored. "
             "In pivots the figure is the average of the row rates.")
    last_session_date = fields.Date(string='Last Session', readonly=True)
    at_risk = fields.Boolean(
        string='Below Threshold', compute='_compute_at_risk',
        search='_search_at_risk')

    def _compute_at_risk(self):
        threshold = self.env['school.student']._attendance_threshold()
        for rec in self:
            counted = rec.present_count + rec.absent_count
            rec.at_risk = bool(counted) and rec.attendance_rate < threshold

    def _search_at_risk(self, operator, value):
        threshold = self.env['school.student']._attendance_threshold()
        positive = (operator == '=') == bool(value)
        if positive:
            return [('attendance_rate', '<', threshold)]
        return [
            '|', ('attendance_rate', '>=', threshold),
            '&', ('present_count', '=', 0), ('absent_count', '=', 0),
        ]

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT row_number() OVER () AS id, agg.*,
                       CASE WHEN agg.present_count + agg.absent_count = 0 THEN NULL
                            ELSE ROUND(agg.present_count * 100.0
                                       / (agg.present_count + agg.absent_count), 2)
                       END AS attendance_rate
                  FROM (
                    SELECT l.student_id,
                           s.course_id,
                           s.department_id,
                           s.unit_id,
                           s.academic_term_id,
                           s.company_id,
                           COUNT(l.id) AS session_count,
                           SUM(CASE WHEN st.is_present THEN 1 ELSE 0 END) AS present_count,
                           SUM(CASE WHEN NOT st.is_present AND st.counts_in_rate
                                    THEN 1 ELSE 0 END) AS absent_count,
                           SUM(CASE WHEN NOT st.is_present AND NOT st.counts_in_rate
                                    THEN 1 ELSE 0 END) AS excused_count,
                           MAX(s.date) AS last_session_date
                      FROM umti_attendance_line l
                      JOIN umti_attendance_sheet s ON s.id = l.sheet_id AND s.state = 'done'
                      JOIN umti_attendance_status st ON st.id = l.status_id
                  GROUP BY l.student_id, s.course_id, s.department_id,
                           s.unit_id, s.academic_term_id, s.company_id
                  ) agg
            )""" % self._table)
