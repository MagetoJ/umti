from odoo.addons.umti_exams.tests.common import ExamsCommon
from odoo.tests import Form, tagged


@tagged('post_install', '-at_install', 'umti_infrastructure')
class TestExamScheduleFetch(ExamsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.hall = env['umti.facility'].create({'name': 'Hall A', 'code': 'HA'})
        # 2026-11-23 is a Monday.
        cls.monday = '2026-11-23'
        Slot = env['umti.timetable.slot']
        Slot.search([('day_of_week', '=', '0'), ('slot_type', 'in', ['exam', 'both'])]).unlink()
        cls.slot_8 = Slot.create({'day_of_week': '0', 'start_time': 8.0, 'end_time': 10.0, 'slot_type': 'exam'})
        cls.slot_11 = Slot.create({'day_of_week': '0', 'start_time': 11.0, 'end_time': 13.0, 'slot_type': 'exam'})

    def _new_schedule(self, assessment, **extra):
        vals = {'assessment_id': assessment.id, 'invigilator_id': False}
        vals.update(extra)
        return self.env['umti.exam.schedule'].create(vals)

    def test_assessment_date_time_venue_are_fetched(self):
        a = self._assessment(date=self.monday, start_time=11.0, end_time=13.0, facility_id=self.hall.id)
        rec = self._new_schedule(a)
        self.assertEqual(str(rec.exam_date), self.monday)
        self.assertEqual(rec.course_id, self.course)
        self.assertEqual(rec.academic_term_id, self.sem1)
        self.assertEqual(rec.unit_id, self.unit)
        self.assertEqual(rec.facility_id, self.hall)
        self.assertEqual(rec.slot_id, self.slot_11, "slot must match the assessment's start time")

    def test_unit_date_overrides_assessment_date(self):
        a = self._assessment(date='2026-11-20', unit_id=False)
        line = a.unit_schedule_ids.filtered(lambda l: l.unit_id == self.unit2)
        line.write({'date': self.monday, 'start_time': 8.0, 'end_time': 10.0})
        rec = self._new_schedule(a, unit_id=self.unit2.id)
        self.assertEqual(str(rec.exam_date), self.monday)
        self.assertEqual(rec.slot_id, self.slot_8)

    def test_changing_unit_refetches_its_date(self):
        a = self._assessment(date='2026-11-20', unit_id=False)
        a.unit_schedule_ids.filtered(lambda l: l.unit_id == self.unit2).write({'date': self.monday})
        rec = self._new_schedule(a, unit_id=self.unit.id)
        self.assertEqual(str(rec.exam_date), '2026-11-20')
        rec.unit_id = self.unit2
        self.assertEqual(str(rec.exam_date), self.monday)

    def test_no_date_on_assessment_is_not_invented(self):
        a = self._assessment(date=False)
        sched = self.env['umti.exam.schedule'].new({'assessment_id': a.id})
        self.assertFalse(sched.exam_date, "must not silently default to today")
        self.assertIn('no exam date', sched.schedule_note)

    def test_form_fills_in_on_picking_the_assessment(self):
        a = self._assessment(date=self.monday, facility_id=self.hall.id)
        form = Form(self.env['umti.exam.schedule'])
        form.assessment_id = a
        self.assertEqual(str(form.exam_date), self.monday)
        self.assertEqual(form.facility_id, self.hall)
        self.assertEqual(form.slot_id, self.slot_8)
        self.assertIn('Fetched from assessment', form.schedule_note)
