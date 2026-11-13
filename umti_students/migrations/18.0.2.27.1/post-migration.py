def migrate(cr, version):
    """Clear the deleted dashboard action from the Student Services menu."""
    if not version:
        return
    cr.execute("""
        UPDATE ir_ui_menu menu
           SET action = NULL
         WHERE menu.id IN (
             SELECT res_id FROM ir_model_data
              WHERE module = 'umti_students'
                AND name = 'menu_school_student_services'
                AND model = 'ir.ui.menu'
         )
    """)
