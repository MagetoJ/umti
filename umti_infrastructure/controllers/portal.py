from odoo import http
from odoo.http import request


class UmtiTimetablePortal(http.Controller):
    """Timetable page shared by students and trainers.

    Students see the classes of the units they are enrolled in (plus their
    published exams); trainers see the classes assigned to them. Records are
    read with sudo, but only ever for the logged-in user's own links.
    """

    @http.route('/my/timetable', type='http', auth='user', website=True)
    def my_timetable(self, **kw):
        env = request.env
        user = env.user
        Schedule = env['umti.class.schedule'].sudo()
        Exam = env['umti.exam.schedule'].sudo()

        student = env['school.student'].sudo().search(
            [('user_id', '=', user.id)], limit=1)
        student_schedules = student.class_schedule_ids if student else Schedule
        student_exams = Exam
        if student:
            enrollments = env['umti.student.unit.enrollment'].sudo().search([
                ('student_id', '=', student.id), ('state', '=', 'enrolled')])
            student_exams = Exam.search([
                ('unit_id', 'in', enrollments.unit_id.ids),
                ('academic_term_id', 'in', enrollments.academic_term_id.ids),
                ('status', '=', 'published'),
            ], order='exam_date')

        trainer_schedules = Schedule.search([('trainer_id', '=', user.id)])
        invigilation = Exam.search([
            ('invigilator_id', '=', user.id),
            ('status', 'in', ['confirmed', 'published']),
        ], order='exam_date')

        return request.render('umti_infrastructure.portal_my_timetable', {
            'page_name': 'timetable',
            'student': student,
            'student_schedules': student_schedules,
            'student_exams': student_exams,
            'trainer_schedules': trainer_schedules,
            'invigilation': invigilation,
        })
