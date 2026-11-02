import base64
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

#: The seven document slots the old model hardcoded, mapped to requirement
#: codes. ``other`` is kept so anything previously parked in the free-form
#: "other document" field survives.
LEGACY_SLOTS = (
    ('kcse', 'KCSE Certificate', 'kcse'),
    ('kcpe', 'KCPE Certificate', 'kcpe'),
    ('leaving', 'Leaving Certificate', 'leaving'),
    ('national_id', 'National ID', 'national_id'),
    ('passport', 'Passport', 'passport'),
    ('birth_cert', 'Birth Certificate', 'birth_cert'),
    ('other', 'Other Document', 'other'),
)

#: slot -> (binary column, filename column, verified column or None)
SLOT_COLUMNS = {
    'kcse': ('kcse_certificate', 'kcse_certificate_name',
             'kcse_certificate_verified'),
    'kcpe': ('kcpe_certificate', 'kcpe_certificate_name',
             'kcpe_certificate_verified'),
    'leaving': ('leaving_certificate', 'leaving_certificate_name',
                'leaving_certificate_verified'),
    'national_id': ('national_id', 'national_id_name', 'national_id_verified'),
    'passport': ('passport', 'passport_name', 'passport_verified'),
    'birth_cert': ('birth_certificate', 'birth_certificate_name',
                   'birth_certificate_verified'),
    'other': ('other_document', 'other_document_name', None),
}


def _column_exists(cr, table, column):
    cr.execute(
        """SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s""",
        (table, column))
    return bool(cr.fetchone())


def _encode(value):
    """bytea -> base64 as expected by a Binary field."""
    if not value:
        return False
    if isinstance(value, memoryview):
        value = value.tobytes()
    return base64.b64encode(value)


def _requirement(env, code, name, company_id):
    Requirement = env['umti.course.required.documents']
    requirement = Requirement.search(
        [('code', '=', code), ('company_id', '=', company_id)], limit=1)
    if not requirement:
        # Someone may already maintain a requirement with that name (the old
        # free-form "other document" slot for instance): reuse it.
        requirement = Requirement.search(
            [('name', '=', name), ('company_id', '=', company_id)], limit=1)
    if not requirement:
        requirement = Requirement.create({
            'name': name,
            'code': code,
            'company_id': company_id,
        })
    return requirement


LEGACY_NAME_TO_CODE = {
    'kcse certificate': 'kcse',
    'kcpe certificate': 'kcpe',
    'leaving certificate': 'leaving',
    'national id': 'national_id',
    'passport': 'passport',
    'birth certificate': 'birth_cert',
}


def _ensure_codes(env):
    """Backfill ``code`` when only this module is upgraded.

    ``umti_core`` owns the field, but the mapping between the old display
    names and the stable codes is an admissions concern.
    """
    Requirement = env['umti.course.required.documents']
    if 'code' not in Requirement._fields:
        return
    for requirement in Requirement.search([('code', '=', False)]):
        code = LEGACY_NAME_TO_CODE.get(
            (requirement.name or '').strip().lower())
        if not code:
            code = (requirement.name or 'document').strip().lower()
            code = ''.join(
                char if char.isalnum() else '_' for char in code).strip('_')
        if Requirement.search_count([
                ('code', '=', code),
                ('company_id', '=', requirement.company_id.id)]):
            continue
        requirement.write({'code': code})


def _legacy_application_columns():
    columns = []
    for slot, _name, _code in LEGACY_SLOTS:
        binary, filename, verified = SLOT_COLUMNS[slot]
        columns += [
            binary, filename, verified,
            '%s_waiver_requested' % binary,
            '%s_waiver_reason' % binary,
            '%s_waived' % binary,
        ]
    return [column for column in columns if column]


def _migrate_application_documents(cr, env):
    """Turn each legacy hardcoded field into a document line."""
    binary, _filename, _verified = SLOT_COLUMNS['kcse']
    if not _column_exists(cr, 'school_admission_application', binary):
        return
    if not _column_exists(cr, 'school_admission_application', 'other_document'):
        # The hardcoded fields are already gone: nothing to carry over.
        return

    Line = env['school.admission.document']
    existing = {
        (line.application_id.id, line.requirement_id.id)
        for line in Line.search([])
    }
    created = 0
    for slot, name, code in LEGACY_SLOTS:
        binary, filename, verified = SLOT_COLUMNS[slot]
        columns = ['id', 'company_id', binary, filename,
                   '%s_waiver_requested' % binary,
                   '%s_waiver_reason' % binary,
                   '%s_waived' % binary]
        if verified:
            columns.append(verified)
        cr.execute("SELECT %s FROM school_admission_application"
                   % ", ".join(columns))
        for row in cr.fetchall():
            (application_id, company_id, attachment, attachment_name,
             waiver_requested, waiver_reason, waived) = row[:7]
            is_verified = row[7] if verified else False
            if not (attachment or is_verified or waiver_requested
                    or waiver_reason or waived):
                continue
            requirement = _requirement(env, code, name, company_id)
            key = (application_id, requirement.id)
            if key in existing:
                continue
            Line.create({
                'application_id': application_id,
                'requirement_id': requirement.id,
                'attachment': _encode(attachment),
                'filename': attachment_name,
                'verified': bool(is_verified),
                'waiver_requested': bool(waiver_requested),
                'waiver_reason': waiver_reason,
                'waived': bool(waived),
            })
            existing.add(key)
            created += 1
    _logger.info("Admissions: carried over %s document line(s).", created)


def _migrate_student_documents(cr, env):
    """Point the student's document list at a requirement."""
    if not _column_exists(cr, 'school_student_document', 'document_type'):
        return
    codes = {slot: code for slot, _name, code in LEGACY_SLOTS}
    names = {slot: name for slot, name, _code in LEGACY_SLOTS}
    cr.execute("""
        SELECT doc.id, doc.document_type, student.company_id
          FROM school_student_document doc
          JOIN school_student student ON student.id = doc.student_id
    """)
    Document = env['school.student.document']
    for document_id, document_type, company_id in cr.fetchall():
        slot = document_type if document_type in codes else 'other'
        requirement = _requirement(env, codes[slot], names[slot], company_id)
        Document.browse(document_id).write({'requirement_id': requirement.id})


def _drop_legacy_columns(cr):
    for column in _legacy_application_columns():
        if _column_exists(cr, 'school_admission_application', column):
            cr.execute('ALTER TABLE school_admission_application '
                       'DROP COLUMN "%s"' % column)
    if _column_exists(cr, 'school_student_document', 'document_type'):
        cr.execute('ALTER TABLE school_student_document '
                   'DROP COLUMN "document_type"')


def migrate(cr, version):
    """Move the hardcoded admission documents onto requirement lines."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'school.admission.document' not in env:
        return
    _ensure_codes(env)
    _migrate_application_documents(cr, env)
    _migrate_student_documents(cr, env)
    # Applications that never touched a document still have to show what the
    # course asks for, otherwise "missing documents" would look empty. The
    # same pass also creates the qualifying/general requirement lines.
    env['school.admission.application'].search([])._sync_requirement_lines()
    # PostgreSQL DDL is transactional: the whole upgrade rolls back together.
    _drop_legacy_columns(cr)
