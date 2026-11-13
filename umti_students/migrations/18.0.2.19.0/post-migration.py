def migrate(cr, version):
    """Link existing payments to their student for the finance lists."""
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'account_payment' "
        "AND column_name = 'umti_student_id'")
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE account_payment payment
           SET umti_student_id = student.id,
               umti_course_id = student.course_id
          FROM school_student student
         WHERE student.partner_id = payment.partner_id
           AND payment.umti_student_id IS NULL
    """)


def _link_manager_group(cr):
    """Existing manager groups are noupdate; add finance explicitly."""
    cr.execute("""
        INSERT INTO res_groups_implied_rel (gid, hid)
        SELECT manager.res_id, finance.res_id
          FROM ir_model_data manager
          JOIN ir_model_data finance
            ON finance.module = 'umti_students'
           AND finance.model = 'res.groups'
           AND finance.name = 'group_umti_student_finance'
         WHERE manager.module = 'umti_students'
           AND manager.model = 'res.groups'
           AND manager.name = 'group_umti_students_manager'
           AND NOT EXISTS (
               SELECT 1 FROM res_groups_implied_rel rel
                WHERE rel.gid = manager.res_id
                  AND rel.hid = finance.res_id
           )
    """)


# Re-open migrate to include the group link.
_original_migrate = migrate


def migrate(cr, version):
    _original_migrate(cr, version)
    if version:
        _link_manager_group(cr)
