def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Move single values into the new many2many fee-line relations."""
    if not version:
        return
    moves = (
        ('course_id', 'umti_fee_structure_line_course_rel', 'course_id'),
        ('academic_year_id',
         'umti_fee_structure_line_academic_year_rel', 'academic_year_id'),
        ('semester_id', 'umti_fee_structure_line_term_rel', 'term_id'),
        ('department_id',
         'umti_fee_structure_line_department_rel', 'department_id'),
    )
    for old_column, relation, target_column in moves:
        if not _column_exists(
                cr, 'umti_fee_structure_line', old_column):
            continue
        cr.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (relation,))
        if not cr.fetchone():
            continue
        cr.execute("""
            INSERT INTO %(relation)s (line_id, %(target)s)
            SELECT line.id, line.%(old)s
              FROM umti_fee_structure_line line
             WHERE line.%(old)s IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM %(relation)s rel
                    WHERE rel.line_id = line.id
                      AND rel.%(target)s = line.%(old)s
               )
        """ % {
            'relation': relation,
            'target': target_column,
            'old': old_column,
        })
    # Recompute the period key from the terms now attached to each line.
    cr.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'umti_fee_structure_line_term_rel'")
    if cr.fetchone() and _column_exists(
            cr, 'umti_fee_structure_line', 'period_sequence'):
        cr.execute("""
            UPDATE umti_fee_structure_line line
               SET period_sequence = COALESCE((
                   SELECT CASE WHEN COUNT(DISTINCT term.sequence) = 1
                               THEN MAX(term.sequence) ELSE 0 END
                     FROM umti_fee_structure_line_term_rel rel
                     JOIN umti_academic_term term
                       ON term.id = rel.term_id
                    WHERE rel.line_id = line.id
               ), 0)
        """)
    for old_column, _relation, _target in moves:
        if _column_exists(cr, 'umti_fee_structure_line', old_column):
            cr.execute(
                "ALTER TABLE umti_fee_structure_line "
                "DROP COLUMN %s" % old_column)
