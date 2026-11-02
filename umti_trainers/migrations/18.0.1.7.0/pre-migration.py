def migrate(cr, version):
    """Snapshot the per-enrollment trainers before the field becomes a
    derived (related) value, so the post-migration can rebuild them as unit
    trainer assignments."""
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS umti_enrollment_trainer_backup")
    cr.execute("""
        CREATE TABLE umti_enrollment_trainer_backup AS
        SELECT unit_id,
               academic_term_id,
               trainer_id,
               COUNT(*) AS total
          FROM umti_student_unit_enrollment
         WHERE trainer_id IS NOT NULL
           AND unit_id IS NOT NULL
           AND academic_term_id IS NOT NULL
         GROUP BY unit_id, academic_term_id, trainer_id
    """)
