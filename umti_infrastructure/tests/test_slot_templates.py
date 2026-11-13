from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSlotTemplates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['umti.timetable.slot.template']
        cls.Slot = cls.env['umti.timetable.slot']
        cls.template = cls.Template.create({
            'name': 'Test Day',
            'line_ids': [
                (0, 0, {'name': 'P1', 'start_time': 6.0, 'end_time': 7.0}),
                (0, 0, {'name': 'Lunch', 'line_type': 'break',
                        'start_time': 7.0, 'end_time': 7.5}),
            ],
        })

    def test_slots_generated_per_day_and_breaks_skipped(self):
        p1 = self.template.line_ids.filtered(lambda l: l.name == 'P1')
        self.assertEqual(len(p1.slot_ids), 5)            # Mon-Fri
        self.assertEqual(len(self.template.slot_ids), 5)  # no break slots

    def test_editing_a_line_moves_its_slots_in_place(self):
        line = self.template.line_ids[0]
        before = line.slot_ids
        line.end_time = 6.75
        self.assertEqual(line.slot_ids, before)
        self.assertTrue(all(s.end_time == 6.75 for s in before))

    def test_removing_a_day_archives_the_orphan_slot(self):
        line = self.template.line_ids[0]
        friday = line.slot_ids.filtered(lambda s: s.day_of_week == '4')
        line.day_fri = False
        self.assertFalse(friday.active)
        self.assertEqual(len(line.slot_ids), 4)

    def test_shared_slot_is_not_mutated(self):
        other = self.template.copy()
        mine = self.template.line_ids[0]
        theirs = other.line_ids[0]
        self.assertEqual(mine.slot_ids, theirs.slot_ids)  # reused, not duplicated
        theirs.end_time = 6.75
        self.assertEqual(mine.slot_ids[0].end_time, 7.0)
        self.assertNotEqual(mine.slot_ids, theirs.slot_ids)

    def test_overlap_inside_template_is_refused(self):
        with self.assertRaises(ValidationError):
            self.template.write({'line_ids': [
                (0, 0, {'name': 'Clash', 'start_time': 6.5, 'end_time': 7.5})]})
