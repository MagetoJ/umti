from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Rebuild the existing enrollment trainers as unit trainer assignments
    and repoint the enrollments at them."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT unit_id, academic_term_id, trainer_id, total
          FROM umti_enrollment_trainer_backup
    """)
    rows = cr.fetchall()

    # One assignment per unit/term: keep the trainer most students had.
    best = {}
    for unit_id, term_id, trainer_id, total in rows:
        key = (unit_id, term_id)
        if key not in best or total > best[key][1]:
            best[key] = (trainer_id, total)

    Mapping = env['umti.unit.trainer'].with_context(
        skip_trainer_allocation_check=True).sudo()
    Term = env['umti.academic.term'].sudo()
    for (unit_id, term_id), (trainer_id, _total) in best.items():
        if Mapping.search_count([
                ('unit_id', '=', unit_id),
                ('academic_term_id', '=', term_id)]):
            continue
        term = Term.browse(term_id)
        Mapping.create({
            'unit_id': unit_id,
            'academic_term_id': term_id,
            'academic_year_id': term.academic_year_id.id,
            'trainer_id': trainer_id,
            'company_id': term.company_id.id or env.company.id,
        })

    # Point the enrollments at their assignment; the trainer follows.
    cr.execute("""
        UPDATE umti_student_unit_enrollment e
           SET mapping_id = m.id,
               trainer_id = m.trainer_id
          FROM umti_unit_trainer m
         WHERE m.unit_id = e.unit_id
           AND m.academic_term_id = e.academic_term_id
    """)
    cr.execute("""
        UPDATE umti_student_unit_enrollment
           SET mapping_id = NULL,
               trainer_id = NULL
         WHERE mapping_id IS NULL
    """)
    cr.execute("DROP TABLE IF EXISTS umti_enrollment_trainer_backup")
    env.invalidate_all()
