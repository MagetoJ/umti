def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Link existing intake invoices to their student and term."""
    if not version:
        return
    if not _column_exists(cr, 'account_move', 'umti_student_id'):
        return
    cr.execute("""
        UPDATE account_move move
           SET umti_student_id = application.student_id,
               umti_academic_term_id = intake.semester_id,
               umti_fee_period_sequence = term.sequence,
               umti_invoice_kind = 'intake',
               umti_course_id = application.course_id,
               umti_academic_year_id = intake.academic_year_id,
               umti_student_state = student.state
          FROM school_admission_application application
          JOIN school_admission_intake intake
            ON intake.id = application.intake_id
          LEFT JOIN umti_academic_term term
            ON term.id = intake.semester_id
          LEFT JOIN school_student student
            ON student.id = application.student_id
         WHERE application.student_id IS NOT NULL
           AND move.id IN (
               application.adm_fee_invoice_id,
               application.refundable_invoice_id,
               application.normal_invoice_id
           )
    """)
