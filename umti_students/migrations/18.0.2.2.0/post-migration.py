def migrate(cr, version):
    """Backfill the term sequence on existing fee records."""
    if not version:
        return
    cr.execute("SELECT 1 FROM information_schema.columns "
               "WHERE table_name = 'umti_fee_record' "
               "AND column_name = 'period_sequence'")
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE umti_fee_record record
           SET period_sequence = term.sequence
          FROM umti_academic_term term
         WHERE record.semester_id = term.id
           AND (record.period_sequence IS NULL OR record.period_sequence = 0)
    """)
