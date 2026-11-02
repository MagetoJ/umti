from odoo.tests.common import TransactionCase


class ExamsCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        dept = env['umti.department'].create({'name': 'ICT', 'code': 'ICT'})
        level = env['umti.course.level'].create({'name': 'Diploma'})
        cls.unit = env['umti.course.units'].create({'name': 'Databases', 'code': 'DB1', 'credit_contribution': 3})
        cls.unit2 = env['umti.course.units'].create({'name': 'Networks', 'code': 'NW1', 'credit_contribution': 3})
        cls.other_unit = env['umti.course.units'].create({'name': 'Law', 'code': 'LW1', 'credit_contribution': 1})
        cls.course = env['umti.course'].create({
            'name': 'Diploma in IT', 'code': 'DIT', 'department_id': dept.id,
            'course_level_id': level.id, 'minimum_credits': 1,
            'unit_ids': [(6, 0, (cls.unit + cls.unit2).ids)]})
        cls.year = env['umti.academic.year'].create({
            'start_date': '2026-10-05', 'end_date': '2027-09-30'})
        cls.sem1 = env['umti.academic.term'].create({
            'name': 'Semester 1', 'term_start_date': '2026-10-05',
            'term_end_date': '2027-01-30', 'academic_year_id': cls.year.id})
        cls.sem2 = env['umti.academic.term'].create({
            'name': 'Semester 2', 'term_start_date': '2027-02-02',
            'term_end_date': '2027-06-30', 'academic_year_id': cls.year.id})
        cls.alice = cls._student('Alice')
        cls.bob = cls._student('Bob')
        cls.manager = env['res.users'].create({
            'name': 'Exam Manager', 'login': 'exam_manager',
            'groups_id': [(6, 0, [env.ref('umti_exams.group_umti_exams_manager').id])]})
        cls.clerk = env['res.users'].create({
            'name': 'Invigilator', 'login': 'exam_clerk',
            'groups_id': [(6, 0, [env.ref('umti_exams.group_umti_exams_user').id])]})

    @classmethod
    def _student(cls, name):
        student = cls.env['school.student'].create({'name': name, 'course_id': cls.course.id})
        student.state = 'active'
        return student

    def _enable_type(self, kind, semester=None):
        """Enable an optional assessment type in the department's plan."""
        plan = self.env['umti.assessment.plan']._get_or_create(
            semester or self.sem1, self.course.department_id)
        plan.line_ids.filtered(lambda l: l.assessment_type == kind).write({'enabled': True})

    def _assessment(self, **vals):
        if vals.get('assessment_type') in ('midterm', 'quiz', 'practical', 'project'):
            self._enable_type(
                vals['assessment_type'],
                self.env['umti.academic.term'].browse(vals['semester_id'])
                if vals.get('semester_id') else None)
        values = {
            'name': 'Test', 'course_id': self.course.id, 'unit_id': self.unit.id,
            'academic_year_id': self.year.id, 'semester_id': self.sem1.id,
            'assessment_type': 'cat', 'max_marks': 100, 'weight': 40,
            'date': '2026-11-20', 'start_time': 9.0, 'end_time': 11.0,
        }
        values.update(vals)
        return self.env['umti.assessment'].create(values)

    def _mark_all(self, assessment, marks_by_student, close=True):
        assessment.action_open()
        for line in assessment.mark_ids:
            line.write({'marks': marks_by_student.get(line.student_id, 0.0)})
        if close:
            assessment.action_close()

    def _publish(self, assessment):
        assessment.action_verify_all()
        assessment.action_publish_all()
