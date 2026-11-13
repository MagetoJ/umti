def migrate(cr, version):
    """Give applications already in review a row in the review queue."""
    if not version:
        return
    cr.execute("SELECT 1 FROM information_schema.tables "
               "WHERE table_name = 'school_admission_review'")
    if not cr.fetchone():
        return
    cr.execute("""
        INSERT INTO school_admission_review
            (application_id, reviewer_id, review_start_date, state,
             create_uid, write_uid, create_date, write_date)
        SELECT application.id,
               COALESCE(application.reviewed_by, application.create_uid, 1),
               COALESCE(application.review_date, CURRENT_DATE),
               CASE WHEN application.state = 'review'
                    THEN 'under_review' ELSE 'received' END,
               1, 1, NOW(), NOW()
          FROM school_admission_application application
         WHERE application.state IN ('submitted', 'review')
           AND NOT EXISTS (
               SELECT 1 FROM school_admission_review review
                WHERE review.application_id = application.id
           )
    """)
