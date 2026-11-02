from odoo.tests import tagged

from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestPortal(ExamsCommon):

    def test_template_shows_only_published_marks_of_own_student(self):
        portal_user = self.env['res.users'].create({
            'name': 'Alice Portal', 'login': 'alice_portal',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.alice.user_id = portal_user
        published = self._assessment(name='PUBLISHED-CAT', weight=50)
        hidden = self._assessment(name='HIDDEN-QUIZ', assessment_type='quiz', weight=20)
        for a in (published, hidden):
            self._mark_all(a, {self.alice: 66, self.bob: 55})
        self._publish(published)
        hidden.mark_ids.with_user(self.manager).action_verify()  # verified, not published
        student = self.env['school.student'].sudo().search([('user_id', '=', portal_user.id)], limit=1)
        html = str(self.env['ir.qweb'].with_user(portal_user)._render(
            'umti_exams.portal_assessment_marks', {'student': student}))
        self.assertIn('PUBLISHED-CAT', html)
        self.assertNotIn('HIDDEN-QUIZ', html)
        self.assertNotIn('Bob', html)
        self.assertIn('66.0', html)
        self.assertEqual(student.published_mark_ids.mapped('assessment_id.name'), ['PUBLISHED-CAT'])

    def test_transcript_renders(self):
        for kind in ('cat', 'assignment', 'final'):
            a = self._assessment(assessment_type=kind)
            self._mark_all(a, {self.alice: 72, self.bob: 40})
            self._publish(a)
        self.env['umti.unit.result'].search([('student_id', '=', self.alice.id)]).with_user(
            self.manager).action_publish()
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'umti_exams.report_transcript', self.alice.ids)
        self.assertIn(b'Databases', html)
