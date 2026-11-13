def migrate(cr, version):
    """Give existing intake terms the new course/start-month name."""
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'umti_academic_term' "
        "AND column_name = 'intake_id'")
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE umti_academic_term term
           SET name = course.name || ' - ' || term.name || ' (' ||
                      to_char(term.term_start_date, 'Mon YYYY') || ')'
          FROM umti_course course
         WHERE term.course_id = course.id
           AND term.intake_id IS NOT NULL
           AND term.term_start_date IS NOT NULL
           AND term.name NOT LIKE course.name || ' - %'
    """)
