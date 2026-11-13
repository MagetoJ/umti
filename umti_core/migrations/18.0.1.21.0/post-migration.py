ORDER = (
    'ADMISSION', 'TUITION', 'BOARDING_EQUIPMENT', 'BOARDING_MEALS',
    'ACTIVITY', 'REPAIRS', 'MEDICAL', 'UTILITIES', 'LOCAL_TRANSPORT',
    'ADMIN', 'EXAM', 'REGISTRATION', 'LIBRARY', 'LABORATORY', 'ICT',
    'DEVELOPMENT', 'CAUTION', 'ATTACHMENT', 'GRADUATION', 'UNIFORM',
    'SECURITY', 'CLEANING', 'SPORTS', 'COUNSELLING', 'WELFARE',
)


def migrate(cr, version):
    """Give the seeded voteheads a default order and one-time flags."""
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'umti_structure_votehead' "
        "AND column_name = 'sequence'")
    if not cr.fetchone():
        return
    for index, code in enumerate(ORDER):
        cr.execute(
            "UPDATE umti_structure_votehead SET sequence = %s "
            "WHERE code = %s",
            ((index + 1) * 10, code))
    cr.execute(
        "UPDATE umti_structure_votehead SET paid_once = TRUE "
        "WHERE code IN ('ADMISSION', 'CAUTION')")
    cr.execute(
        "UPDATE umti_structure_votehead SET refundable = TRUE "
        "WHERE code = 'CAUTION'")
