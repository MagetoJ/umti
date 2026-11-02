from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestAssessmentPlan(ExamsCommon):

    def _plan(self, semester=None):
        return self.env['umti.assessment.plan'].search([
            ('semester_id', '=', (semester or self.sem1).id),
            ('department_id', '=', self.course.department_id.id)])

    def _line(self, plan, kind):
        return plan.line_ids.filtered(lambda l: l.assessment_type == kind)

    def test_default_plan_is_cat_assignment_final(self):
        plan = self._plan()
        self.assertEqual(len(plan), 1)                       # created with the semester
        self.assertEqual(plan.core_weights(), {'cat': 20.0, 'assignment': 10.0, 'final': 70.0})
        self.assertEqual(plan.core_weight_total, 100)
        self.assertEqual(plan.enabled_types(), {'cat', 'assignment', 'final'})

    def test_core_weights_must_total_100(self):
        plan = self._plan()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._line(plan, 'cat').weight = 30
        # changing two lines together is fine as long as the total is 100
        plan.write({'line_ids': [
            (1, self._line(plan, 'cat').id, {'weight': 30}),
            (1, self._line(plan, 'final').id, {'weight': 60})]})
        self.assertEqual(plan.core_weights(), {'cat': 30.0, 'assignment': 10.0, 'final': 60.0})

    def test_core_types_cannot_be_disabled_and_optional_cannot_weigh(self):
        plan = self._plan()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._line(plan, 'final').enabled = False
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._line(plan, 'quiz').weight = 10

    def test_disabled_type_blocked_enabled_type_allowed(self):
        vals = {
            'name': 'Practical', 'course_id': self.course.id, 'unit_id': self.unit.id,
            'academic_year_id': self.year.id, 'semester_id': self.sem1.id,
            'assessment_type': 'practical', 'max_marks': 50}
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['umti.assessment'].create(vals)
        self._line(self._plan(), 'practical').enabled = True
        self.assertTrue(self.env['umti.assessment'].create(vals))
        # cannot be switched off again while an assessment of that type exists
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._line(self._plan(), 'practical').enabled = False

    def test_changing_weights_recomputes_results(self):
        for kind in ('cat', 'assignment', 'final'):
            a = self._assessment(assessment_type=kind)
            self._mark_all(a, {self.alice: 100 if kind == 'final' else 0, self.bob: 0})
            self._publish(a)
        result = self.env['umti.unit.result'].search([
            ('student_id', '=', self.alice.id), ('unit_id', '=', self.unit.id)])
        self.assertAlmostEqual(result.final_mark, 70)
        plan = self._plan()
        plan.write({'line_ids': [
            (1, self._line(plan, 'cat').id, {'weight': 30}),
            (1, self._line(plan, 'final').id, {'weight': 60})]})
        self.assertAlmostEqual(result.final_mark, 60)

    def test_each_department_has_its_own_plan(self):
        other = self.env['umti.department'].create({'name': 'Engineering', 'code': 'ENG'})
        plan = self.env['umti.assessment.plan']._get_or_create(self.sem1, other)
        self._line(plan, 'quiz').enabled = True
        self.assertIn('quiz', plan.enabled_types())
        self.assertNotIn('quiz', self._plan().enabled_types())
        with self.assertRaises(Exception), self.cr.savepoint():
            self.env['umti.assessment.plan'].create(
                {'semester_id': self.sem1.id, 'department_id': other.id})

    def test_hod_edits_own_department_only_and_confirm_locks(self):
        hod = self.env['res.users'].create({
            'name': 'HOD ICT', 'login': 'hod_ict',
            'groups_id': [(6, 0, [self.env.ref('umti_exams.group_umti_exams_hod').id])]})
        self.course.department_id.manager_id = hod
        other = self.env['umti.department'].create({'name': 'Engineering', 'code': 'ENG'})
        other_plan = self.env['umti.assessment.plan']._get_or_create(self.sem1, other)
        plan = self._plan()

        with self.assertRaises(AccessError):
            self._line(other_plan, 'quiz').with_user(hod).enabled = True
        with self.assertRaises(AccessError):
            self._line(plan, 'quiz').with_user(self.clerk).enabled = True

        self._line(plan, 'quiz').with_user(hod).enabled = True
        plan.with_user(hod).action_confirm()
        self.assertEqual(plan.state, 'confirmed')
        with self.assertRaises(UserError):
            self._line(plan, 'project').with_user(hod).enabled = True
        with self.assertRaises(AccessError):
            plan.with_user(hod).action_reset_draft()           # managers only
        plan.with_user(self.manager).action_reset_draft()
        self.assertEqual(plan.state, 'draft')

    def test_starting_semester_confirms_plans(self):
        self.sem1.action_activate_academic_term()
        self.assertEqual(self._plan().state, 'confirmed')
