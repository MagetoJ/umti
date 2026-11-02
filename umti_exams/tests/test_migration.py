from odoo.tests import tagged

from ..scripts.migrate_from_umti_examinations import migrate
from .common import ExamsCommon


@tagged('post_install', '-at_install', 'umti_exams')
class TestMigration(ExamsCommon):

    def _legacy_tables(self):
        self.env.cr.execute("""
            CREATE TABLE mig_exam (id int, name varchar, code varchar, course_id int, unit_id int,
                academic_year varchar, semester varchar, venue varchar, exam_date date,
                start_time float, end_time float, category varchar, exam_type varchar,
                max_marks float, pass_marks float, state varchar, company_id int, active bool);
            CREATE TABLE mig_line (id int, exam_id int, student_id int, marks_obtained float,
                remarks text, state varchar)""")

    def _exam(self, id, code, **kw):
        v = dict(id=id, name='Legacy ' + code, code=code, course_id=self.course.id,
                 unit_id=self.unit.id, academic_year='2026/2027', semester='sem1', venue='Hall',
                 exam_date='2026-11-%02d' % (id + 1), start_time=9.0, end_time=11.0, category='x',
                 exam_type='quiz', max_marks=100.0, pass_marks=50.0, state='completed',
                 company_id=self.env.company.id, active=True)
        v.update(kw)
        cols = ','.join(v)
        self.env.cr.execute('INSERT INTO mig_exam (%s) VALUES (%s)' % (cols, ','.join(['%s'] * len(v))),
                            list(v.values()))

    def _line(self, id, exam_id, student, marks, state='published'):
        self.env.cr.execute(
            'INSERT INTO mig_line VALUES (%s,%s,%s,%s,%s,%s)',
            (id, exam_id, student.partner_id.id, marks, 'ok', state))

    def test_migration_with_skips(self):
        self._legacy_tables()
        self._exam(1, 'OLD-1')                                   # good
        self._exam(2, 'OLD-2', exam_type='final')                # good, earliest final
        self._exam(3, 'OLD-3', exam_type='final', exam_date='2026-12-30')  # second final -> skip
        self._exam(4, 'OLD-4', academic_year='1999/2000')        # unmatched year -> skip
        self._exam(5, 'OLD-5', semester='sem3')                  # sem3 -> skip
        self._exam(6, 'OLD-6', start_time=12.0, end_time=9.0)    # end before start -> skip
        self._exam(7, 'OLD-1')                                   # duplicate code -> skip
        self._exam(8, 'OLD-8', semester='sem2')                  # good, alone in sem2
        self._line(1, 1, self.alice, 70)
        self._line(2, 1, self.alice, 71)                         # duplicate student -> skip
        self._line(3, 1, self.bob, 55, 'verified')
        self._line(4, 4, self.alice, 60)                         # exam skipped -> skip
        report = migrate(self.env, 'mig_exam', 'mig_line', snapshot=False)
        by = {(r['kind'], r['legacy_id']): r for r in report}
        for key in (('exam', 1), ('exam', 2), ('exam', 8), ('line', 1), ('line', 3)):
            self.assertEqual(by[key]['action'], 'MIGRATED', key)
        for key in (('exam', 3), ('exam', 4), ('exam', 5), ('exam', 6), ('exam', 7),
                    ('line', 2), ('line', 4)):
            self.assertEqual(by[key]['action'], 'SKIPPED', key)
            self.assertTrue(by[key]['reason'])
        self.assertEqual(len(report), 8 + 4)  # every row accounted for
        a1 = self.env['umti.assessment'].search([('code', '=', 'OLD-1')])
        a2 = self.env['umti.assessment'].search([('code', '=', 'OLD-2')])
        self.assertEqual((a1.state, a1.assessment_type, a1.category), ('closed', 'quiz', 'periodic'))
        self.assertEqual(a1.weight + a2.weight, 100)
        self.assertIn('weights set equally', by[('exam', 1)]['reason'])
        self.assertEqual(self.env['umti.assessment'].search([('code', '=', 'OLD-8')]).weight, 100)
        marks = {m.student_id: m for m in a1.mark_ids}
        self.assertEqual(marks[self.alice].state, 'published')
        self.assertEqual(marks[self.bob].state, 'verified')
        self.assertEqual(len(a1.mark_ids), 2)
        # unit result stays incomplete: the final exam has no published lines
        res = self.env['umti.unit.result'].search([
            ('student_id', '=', self.alice.id), ('semester_id', '=', self.sem1.id)])
        self.assertFalse(res.is_complete)
