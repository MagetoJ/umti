"""Fold the old regular/exam schedule lines into one list per template."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'umti_slot_template_line'
    """)
    cols = {row[0] for row in cr.fetchall()}
    if 'regular_template_id' not in cols:
        return
    cr.execute("ALTER TABLE umti_slot_template_line "
               "ADD COLUMN IF NOT EXISTS template_id integer")
    cr.execute("ALTER TABLE umti_slot_template_line "
               "ADD COLUMN IF NOT EXISTS line_type varchar")
    cr.execute("""
        UPDATE umti_slot_template_line
           SET template_id = COALESCE(regular_template_id, exam_template_id),
               line_type = CASE WHEN regular_template_id IS NOT NULL
                                THEN 'regular' ELSE 'exam' END
         WHERE template_id IS NULL
    """)
    cr.execute("DELETE FROM umti_slot_template_line WHERE template_id IS NULL")
