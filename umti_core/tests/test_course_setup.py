from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCourseSetupWarning(TransactionCase):
    """The setup banner stays dismissed only until a requirement changes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.department = env['umti.department'].create(
            {'name': 'ICT', 'code': 'ICT'})
        cls.level = env['umti.course.level'].create({'name': 'Diploma'})
        cls.course = env['umti.course'].create({
            'name': 'Diploma in IT',
            'code': 'DIT',
            'department_id': cls.department.id,
            'course_level_id': cls.level.id,
            'minimum_credits': 1,
        })
        cls.document = env['umti.course.required.documents'].create({
            'name': 'National ID', 'code': 'national_id'})
        cls.qualifying = env['umti.course.qualifying.requirement'].create({
            'name': 'KCSE', 'required_mark': 'C+'})
        cls.general = env['umti.course.general.requirement'].create({
            'name': 'Interview'})

    def test_banner_lists_missing_sections_and_dismisses(self):
        self.assertTrue(self.course.show_setup_warning)
        self.assertIn('required documents',
                      self.course.setup_warning_message)
        self.course.action_dismiss_setup_warning()
        self.assertFalse(self.course.show_setup_warning)

    def test_adding_a_requirement_resets_the_dismissal(self):
        self.course.action_dismiss_setup_warning()
        self.course.write(
            {'document_ids': [(4, self.document.id)]})
        self.assertFalse(self.course.requirements_warning_dismissed)
        self.assertTrue(self.course.show_setup_warning)

    def test_editing_a_requirement_resets_the_dismissal(self):
        self.course.write({
            'document_ids': [(4, self.document.id)],
            'qualifying_requirement_ids': [(4, self.qualifying.id)],
            'general_requirement_ids': [(4, self.general.id)],
        })
        self.assertFalse(self.course.show_setup_warning)
        self.course.action_dismiss_setup_warning()
        self.document.name = 'National Identity Card'
        self.assertFalse(self.course.requirements_warning_dismissed)
