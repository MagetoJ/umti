def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE umti_student_service_type
           SET active = FALSE
         WHERE code = 'accommodation'
    """)
