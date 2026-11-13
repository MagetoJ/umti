def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Prepare data so the new constraints and required fields can be created.

    * Enrollment: the legacy free-text ``academic_term`` is gone; try to map it
      to ``academic_term_id`` by name, relax its NOT NULL, and drop duplicate
      draft rows created by the old ``fill_enrollment`` button so that
      UNIQUE(student_id, unit_id, academic_term_id) can be created.
    * Attendance lines: remove duplicate students on one sheet (keep the first)
      before UNIQUE(sheet_id, student_id) is created.
    """
    if _column_exists(cr, 'umti_student_unit_enrollment', 'academic_term'):
        cr.execute("""
            UPDATE umti_student_unit_enrollment e
               SET academic_term_id = t.id
              FROM umti_academic_term t
             WHERE e.academic_term_id IS NULL
               AND e.academic_term IS NOT NULL
               AND lower(t.name) = lower(e.academic_term)
        """)
        cr.execute(
            "ALTER TABLE umti_student_unit_enrollment ALTER COLUMN academic_term DROP NOT NULL")

    cr.execute("""
        DELETE FROM umti_student_unit_enrollment e
              USING umti_student_unit_enrollment d
          WHERE e.id > d.id
            AND e.student_id = d.student_id
            AND e.unit_id = d.unit_id
            AND e.academic_term_id IS NOT DISTINCT FROM d.academic_term_id
            AND e.state = 'draft'
    """)

    cr.execute("""
        DELETE FROM umti_attendance_line l
              USING umti_attendance_line d
          WHERE l.id > d.id
            AND l.sheet_id = d.sheet_id
            AND l.student_id = d.student_id
    """)
