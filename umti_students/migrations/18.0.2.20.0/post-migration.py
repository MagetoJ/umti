def migrate(cr, version):
    """Remove the old form action replaced by the OWL client action."""
    if not version:
        return
    cr.execute("""
        DELETE FROM ir_act_window
         WHERE id IN (
             SELECT res_id FROM ir_model_data
              WHERE module = 'umti_students'
                AND name = 'action_umti_student_finance'
                AND model = 'ir.actions.act_window'
         )
    """)
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'umti_students'
           AND name = 'action_umti_student_finance'
           AND model = 'ir.actions.act_window'
    """)
