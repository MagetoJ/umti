def migrate(cr, version):
    """Copy each unit's old single department into its new department set."""
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'umti_course_units_department_rel'")
    if not cr.fetchone():
        return
    cr.execute("""
        INSERT INTO umti_course_units_department_rel
            (unit_id, department_id)
        SELECT unit.id, unit.department_id
          FROM umti_course_units unit
         WHERE unit.department_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
                 FROM umti_course_units_department_rel rel
                WHERE rel.unit_id = unit.id
                  AND rel.department_id = unit.department_id
           )
    """)
