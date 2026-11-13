def migrate(cr, version):
    """All service areas now have dedicated models; retire the old types."""
    if not version:
        return
    cr.execute("""
        UPDATE umti_student_service_type
           SET active = FALSE
    """)
