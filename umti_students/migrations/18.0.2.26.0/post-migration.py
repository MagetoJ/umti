def migrate(cr, version):
    """Existing manager groups are noupdate; add all services explicitly."""
    if not version:
        return
    cr.execute("""
        INSERT INTO res_groups_implied_rel (gid, hid)
        SELECT manager.res_id, service.res_id
          FROM ir_model_data manager
          JOIN ir_model_data service
            ON service.module = 'umti_students'
           AND service.model = 'res.groups'
           AND (service.name = 'group_umti_student_services_user'
                OR service.name LIKE 'group_umti_service_%')
         WHERE manager.module = 'umti_students'
           AND manager.model = 'res.groups'
           AND manager.name = 'group_umti_students_manager'
           AND NOT EXISTS (
               SELECT 1 FROM res_groups_implied_rel rel
                WHERE rel.gid = manager.res_id
                  AND rel.hid = service.res_id
           )
    """)
