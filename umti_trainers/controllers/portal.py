from odoo import http
from odoo.http import request


class UmtiTrainerPortal(http.Controller):

    @http.route('/my/students', type='http', auth='user', website=True)
    def my_students(self, **kw):
        """Students the logged-in trainer is taking through a unit.

        Records are read with sudo but scoped to the trainer's own employee
        record, so a portal trainer only ever sees their own students.
        """
        env = request.env
        employee = env['hr.employee'].sudo().search(
            [('user_id', '=', env.user.id)], limit=1)
        enrollments = env['umti.student.unit.enrollment'].sudo()
        if employee:
            enrollments = enrollments.search([
                ('trainer_id', '=', employee.id),
                ('state', 'in', ('draft', 'enrolled')),
            ], order='academic_term_id, unit_id, student_id')
        return request.render('umti_trainers.portal_my_students', {
            'employee': employee,
            'enrollments': enrollments,
            'page_name': 'my_students',
        })
