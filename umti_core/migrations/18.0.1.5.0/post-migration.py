def migrate(cr, version):
    """Backfill the period key of existing fee structure lines."""
    if not version:
        return
    cr.execute("SELECT 1 FROM information_schema.columns "
               "WHERE table_name = 'umti_fee_structure_line' "
               "AND column_name = 'period_sequence'")
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE umti_fee_structure_line line
           SET period_sequence = term.sequence
          FROM umti_academic_term term
         WHERE line.semester_id = term.id
           AND (line.period_sequence IS NULL OR line.period_sequence = 0)
    """)
