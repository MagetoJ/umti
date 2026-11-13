def migrate(cr, version):
    """Drop the obsolete fee-structure code field and its metadata."""
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'umti_fee_structure' AND column_name = 'code'")
    if not cr.fetchone():
        return
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields'
           AND res_id IN (
               SELECT id FROM ir_model_fields
                WHERE model = 'umti.fee.structure' AND name = 'code'
           )
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE model = 'umti.fee.structure' AND name = 'code'
    """)
    cr.execute("ALTER TABLE umti_fee_structure DROP COLUMN code")
