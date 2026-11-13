from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestUnitDepartments(TransactionCase):
    """A unit can belong to several departments while keeping a primary."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department_one = cls.env['umti.department'].create(
            {'name': 'Engineering', 'code': 'ENG'})
        cls.department_two = cls.env['umti.department'].create(
            {'name': 'Business', 'code': 'BUS'})

    def test_many_departments_keep_a_primary(self):
        unit = self.env['umti.course.units'].create({
            'name': 'Mathematics',
            'code': 'MATH',
            'credit_contribution': 3,
            'department_ids': [(6, 0, (
                self.department_one | self.department_two).ids)],
        })
        self.assertEqual(set(unit.department_ids.ids), {
            self.department_one.id, self.department_two.id})
        self.assertIn(unit.department_id,
                      self.department_one | self.department_two)
        primary = unit.department_id
        unit.write({'department_ids': [(3, primary.id)]})
        self.assertNotEqual(unit.department_id, primary)
        self.assertIn(unit.department_id, unit.department_ids)

    def test_legacy_department_becomes_part_of_the_set(self):
        unit = self.env['umti.course.units'].create({
            'name': 'Communication',
            'code': 'COMM',
            'credit_contribution': 2,
            'department_id': self.department_one.id,
        })
        self.assertIn(self.department_one, unit.department_ids)
        self.assertEqual(unit.department_id, self.department_one)
