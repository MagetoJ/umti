from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged('post_install', '-at_install', 'umti_attendance')
class TestStudentAttendance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        dept = env['umti.department'].create({'name': 'ICT', 'code': 'ICT'})
        level = env['umti.course.level'].create({'name': 'Diploma'})
        cls.unit = env['umti.course.units'].create(
            {'name': 'Databases', 'code': 'DB1', 'credit_contribution': 3})
        cls.course = env['umti.course'].create({
            'name': 'Diploma in IT', 'code': 'DIT', 'department_id': dept.id,
            'course_level_id': level.id, 'minimum_credits': 1,
            'unit_ids': [(6, 0, cls.unit.ids)]})
        year = env['umti.academic.year'].create({
            'start_date': '2026-10-05', 'end_date': '2027-09-30'})
        cls.term = env['umti.academic.term'].create({
            'name': 'Semester 1', 'term_start_date': '2026-10-05',
            'term_end_date': '2027-01-30', 'academic_year_id': year.id})
        cls.dept = dept
        cls.student = env['school.student'].create(
            {'name': 'Alice', 'course_id': cls.course.id})
        cls.present = env.ref('umti_trainers.attendance_status_present')
        cls.absent = env.ref('umti_trainers.attendance_status_absent')
        cls.excused = env.ref('umti_trainers.attendance_status_excused')

    def _sheet(self, status, name, submit=True, day='2026-11-02'):
        sheet = self.env['umti.attendance.sheet'].create({
            'name': name, 'date': day, 'department_id': self.dept.id,
            'course_id': self.course.id, 'unit_id': self.unit.id,
            'academic_term_id': self.term.id,
            'line_ids': [(0, 0, {'student_id': self.student.id, 'status_id': status.id})],
        })
        if submit:
            sheet.action_submit_attendance()
        return sheet

    def test_draft_sheets_do_not_count(self):
        self._sheet(self.present, 'Draft session', submit=False)
        self.assertEqual(self.student.attendance_session_count, 0)
        self.assertEqual(self.student.attendance_state, 'no_data')

    def test_rate_ignores_excused(self):
        self._sheet(self.present, 'S1', day='2026-11-02')
        self._sheet(self.absent, 'S2', day='2026-11-03')
        self._sheet(self.excused, 'S3', day='2026-11-04')
        st = self.student
        self.assertEqual(
            (st.attendance_session_count, st.attendance_present_count,
             st.attendance_absent_count, st.attendance_excused_count), (3, 1, 1, 1))
        self.assertAlmostEqual(st.attendance_rate, 50.0)
        self.assertEqual(st.attendance_state, 'at_risk')
        self.assertIn(st, self.env['school.student'].search(
            [('attendance_at_risk', '=', True)]))

    def test_summary_by_unit_and_hook(self):
        self._sheet(self.present, 'S1', day='2026-11-02')
        self._sheet(self.present, 'S2', day='2026-11-03')
        summary = self.env['umti.attendance.summary'].search(
            [('student_id', '=', self.student.id)])
        self.assertEqual(len(summary), 1)
        self.assertEqual((summary.session_count, summary.attendance_rate), (2, 100.0))
        data = self.student._get_attendance_summary()
        self.assertEqual(data['rate'], 100.0)
        self.assertEqual(data['units'][0]['unit'], self.unit.display_name)

    def test_submitted_sheet_is_locked(self):
        sheet = self._sheet(self.present, 'S1')
        with self.assertRaises(UserError):
            sheet.line_ids.status_id = self.absent
        with self.assertRaises(UserError):
            sheet.write({'name': 'Renamed'})
        sheet.action_reset_draft()
        sheet.line_ids.status_id = self.absent
        self.assertEqual(self.student.attendance_session_count, 0)

    def test_duplicate_sheet_blocked(self):
        self._sheet(self.present, 'Same', submit=False)
        with self.assertRaises(ValidationError):
            self._sheet(self.present, 'Same', submit=False)

    def test_enrollment_unique_per_term(self):
        Enrollment = self.env['umti.student.unit.enrollment']
        vals = {
            'student_id': self.student.id, 'course_id': self.course.id,
            'unit_id': self.unit.id, 'academic_term_id': self.term.id,
            'state': 'enrolled',
        }
        existing = Enrollment.search([
            ('student_id', '=', self.student.id), ('unit_id', '=', self.unit.id),
            ('academic_term_id', '=', self.term.id)])
        if not existing:
            Enrollment.create(vals)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            Enrollment.create(vals)
