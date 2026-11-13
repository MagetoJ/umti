def migrate(cr, version):
    """Alumni now has its own model; retire the generic service type."""
    if not version:
        return
    cr.execute("""
        UPDATE umti_student_service_type
           SET active = FALSE
         WHERE code = 'alumni'
    """)
