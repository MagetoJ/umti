def migrate(cr, version):
    """Seed the new generated name and academic-year summary."""
    if not version:
        return
    cr.execute("""
        UPDATE umti_fee_structure structure
           SET name = CASE structure.status
                          WHEN 'draft' THEN 'Draft'
                          WHEN 'approved' THEN 'Approved'
                          WHEN 'closed' THEN 'Closed'
                          ELSE 'Draft'
                      END || ' Fee Structure for ' || company.name
          FROM res_company company
         WHERE structure.company_id = company.id
    """)
    cr.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'umti_fee_structure_academic_year_rel'")
    if not cr.fetchone():
        return
    cr.execute("""
        INSERT INTO umti_fee_structure_academic_year_rel
            (structure_id, academic_year_id)
        SELECT DISTINCT line.structure_id, line.academic_year_id
          FROM umti_fee_structure_line line
         WHERE line.academic_year_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
                 FROM umti_fee_structure_academic_year_rel rel
                WHERE rel.structure_id = line.structure_id
                  AND rel.academic_year_id = line.academic_year_id
           )
    """)
