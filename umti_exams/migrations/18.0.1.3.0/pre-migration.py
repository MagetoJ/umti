"""Assessment plans are gone: every assessment now carries its own weight.

Runs BEFORE the plan tables are dropped from the registry. For each existing
assessment it works out the share it used to contribute to the final mark
(its department/semester plan weight for the type, split equally between
assessments of the same type for the unit) and stores that in ``weight``.
"""
DEFAULT_WEIGHTS = {'cat': 20.0, 'assignment': 10.0, 'final': 70.0}
CORE = tuple(DEFAULT_WEIGHTS)


def _table_exists(cr, name):
    cr.execute("SELECT to_regclass(%s)", (name,))
    return cr.fetchone()[0] is not None


def migrate(cr, version):
    if not version or not _table_exists(cr, 'umti_assessment'):
        return

    plan_weights = {}
    if _table_exists(cr, 'umti_assessment_plan') and _table_exists(cr, 'umti_assessment_plan_line'):
        cr.execute("""
            SELECT p.semester_id, p.department_id, l.assessment_type, l.weight
              FROM umti_assessment_plan p
              JOIN umti_assessment_plan_line l ON l.plan_id = p.id
             WHERE l.assessment_type IN %s
        """, (CORE,))
        for semester_id, dept_id, kind, weight in cr.fetchall():
            plan_weights[(semester_id, dept_id, kind)] = weight or 0.0

    cr.execute("""
        SELECT id, assessment_type, semester_id, department_id, unit_id, course_id
          FROM umti_assessment
         WHERE state != 'cancelled'
    """)
    rows = cr.fetchall()

    groups = {}
    for _id, kind, sem, dept, unit, course in rows:
        groups.setdefault((unit, sem, course, kind), []).append((_id, sem, dept))

    for (_unit, _sem, _course, kind), members in groups.items():
        if kind not in CORE:
            new_weight = 0.0
        else:
            _id, sem, dept = members[0]
            component = plan_weights.get((sem, dept, kind), DEFAULT_WEIGHTS[kind])
            new_weight = round(component / max(1, len(members)), 4)
        cr.execute(
            "UPDATE umti_assessment SET weight = %s WHERE id IN %s",
            (new_weight, tuple(m[0] for m in members)))

    # Cancelled assessments never count.
    cr.execute("UPDATE umti_assessment SET weight = 0 WHERE state = 'cancelled'")
