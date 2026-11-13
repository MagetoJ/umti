def migrate(cr, version):
    """Rename fee-structure states and regenerate names with their dates."""
    if not version:
        return
    cr.execute("""
        UPDATE umti_fee_structure
           SET status = CASE status
                            WHEN 'draft' THEN 'proposed'
                            WHEN 'approved' THEN 'active'
                            WHEN 'closed' THEN 'historic'
                            ELSE status
                        END
         WHERE status IN ('draft', 'approved', 'closed')
    """)
    cr.execute("""
        UPDATE umti_fee_structure structure
           SET name =
               CASE structure.status
                   WHEN 'proposed' THEN 'Proposed'
                   WHEN 'active' THEN 'Active'
                   WHEN 'historic' THEN 'Historic'
                   ELSE 'Proposed'
               END
               || ' Fee Structure for ' || company.name
               || CASE
                      WHEN structure.active_from IS NOT NULL
                       AND structure.active_to IS NOT NULL
                      THEN ' (' ||
                           to_char(structure.active_from, 'DD Mon YYYY') ||
                           ' - ' ||
                           to_char(structure.active_to, 'DD Mon YYYY') || ')'
                      WHEN structure.active_from IS NOT NULL
                      THEN ' (from ' ||
                           to_char(structure.active_from, 'DD Mon YYYY') || ')'
                      WHEN structure.active_to IS NOT NULL
                      THEN ' (until ' ||
                           to_char(structure.active_to, 'DD Mon YYYY') || ')'
                      ELSE ''
                  END
          FROM res_company company
         WHERE structure.company_id = company.id
    """)
