def migrate(cr, version):
    """Attendance status moved from a fixed selection to configurable records.

    Map each existing line's old code to the matching status record, remove
    the obsolete column (it was NOT NULL and would block new lines), then
    enforce NOT NULL on the new column.
    """
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'umti_attendance_line' AND column_name = 'status'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE umti_attendance_line l
               SET status_id = s.id
              FROM umti_attendance_status s
             WHERE s.code = l.status AND l.status_id IS NULL
        """)
        cr.execute("ALTER TABLE umti_attendance_line DROP COLUMN status")
    cr.execute("""
        UPDATE umti_attendance_line
           SET status_id = (SELECT id FROM umti_attendance_status
                             WHERE is_default ORDER BY id LIMIT 1)
         WHERE status_id IS NULL
    """)
    cr.execute("SELECT 1 FROM umti_attendance_line WHERE status_id IS NULL LIMIT 1")
    if not cr.fetchone():
        cr.execute(
            "ALTER TABLE umti_attendance_line ALTER COLUMN status_id SET NOT NULL")
