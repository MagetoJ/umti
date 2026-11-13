"""Backfill per-course unit placements from the legacy unit fields.

Before this version a unit stored its year and semester on the unit itself
(``unit_level`` / ``unit_semester``), which prevents the same unit from
sitting in different periods of different courses. Every existing course
keeps its current placement by copying those values into a line per unit.
"""

LEVELS = {
    'yr_one': 1,
    'yr_two': 2,
    'yr_three': 3,
    'yr_four': 4,
    'yr_five': 5,
    'yr_six': 6,
    'other': 1,
}

PERIODS = {
    'sem_1': 10,
    'sem_2': 20,
    'sem_3': 30,
    'sem_4': 40,
    'other': 10,
}


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT 1 FROM information_schema.tables "
               "WHERE table_name = 'umti_course_unit_line'")
    if not cr.fetchone():
        return
    level_cases = ' '.join(
        "WHEN %s THEN %s" % (repr(key), value)
        for key, value in LEVELS.items())
    period_cases = ' '.join(
        "WHEN %s THEN %s" % (repr(key), value)
        for key, value in PERIODS.items())
    cr.execute(f"""
        INSERT INTO umti_course_unit_line
            (course_id, unit_id, course_year, period_sequence, phase,
             active, create_uid, write_uid, create_date, write_date)
        SELECT rel.course_id,
               rel.unit_id,
               CASE u.unit_level {level_cases} ELSE 1 END,
               CASE u.unit_semester {period_cases} ELSE 10 END,
               'taught', TRUE, 1, 1, NOW(), NOW()
        FROM umti_course_unit_rel rel
        JOIN umti_course_units u ON u.id = rel.unit_id
        WHERE NOT EXISTS (
            SELECT 1 FROM umti_course_unit_line l
            WHERE l.course_id = rel.course_id
              AND l.unit_id = rel.unit_id
        )
    """)
