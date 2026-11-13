"""Drop the columns of the two removed Many2one fields."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("ALTER TABLE IF EXISTS umti_slot_template_line "
               "DROP COLUMN IF EXISTS regular_template_id, "
               "DROP COLUMN IF EXISTS exam_template_id")
