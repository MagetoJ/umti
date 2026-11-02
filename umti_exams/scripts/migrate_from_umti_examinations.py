"""Migrate the legacy umti_examinations tables into umti_exams.

Run inside an Odoo shell on a database where umti_exams is installed (the legacy
tables umti_exam and umti_student_assessment must still exist):

    docker compose exec -T odoo_web odoo shell -d <db> --no-http < migrate_from_umti_examinations.py

or call migrate(env) from your own code.  Nothing is guessed: every row that
cannot be mapped unambiguously is SKIPPED and listed in the report.  The legacy
tables are snapshotted to <table>_legacy first and are never dropped here.
"""
import re
from collections import defaultdict

from odoo.exceptions import UserError, ValidationError

TYPE_MAP = {'midterm': 'midterm', 'final': 'final', 'quiz': 'quiz', 'practical': 'practical'}
STATE_MAP = {'draft': 'draft', 'scheduled': 'scheduled', 'completed': 'closed', 'cancelled': 'cancelled'}
SEMESTER_INDEX = {'sem1': 0, 'sem2': 1, 'sem3': 2}


def _row(report, kind, legacy_id, code, action, reason=''):
    report.append({'kind': kind, 'legacy_id': legacy_id, 'code': code,
                   'action': action, 'reason': reason})


def migrate(env, exam_table='umti_exam', line_table='umti_student_assessment', snapshot=True):
    cr = env.cr
    report = []
    if snapshot:
        for table in (exam_table, line_table):
            cr.execute('CREATE TABLE IF NOT EXISTS "%s_legacy" AS SELECT * FROM "%s"' % (table, table))
    Assessment = env['umti.assessment'].with_context(umti_migration=True)
    Mark = env['umti.assessment.mark'].with_context(umti_migration=True)

    cr.execute('SELECT * FROM "%s" ORDER BY id' % exam_table)
    exams = cr.dictfetchall()
    cr.execute('SELECT * FROM "%s" ORDER BY id' % line_table)
    lines = cr.dictfetchall()

    # --- decide per exam ------------------------------------------------------
    years = env['umti.academic.year'].search([])
    seen_codes = set()
    plan = {}          # legacy id -> create vals
    skipped = {}       # legacy id -> reason
    for ex in exams:
        reason = None
        code = ex['code']
        key = (code, ex['company_id'])
        if key in seen_codes or (code and env['umti.assessment'].with_context(active_test=False).search_count(
                [('code', '=', code), ('company_id', '=', ex['company_id'])])):
            reason = 'duplicate exam code (or already migrated)'
        seen_codes.add(key)
        match = re.search(r'\d{4}', ex.get('academic_year') or '')
        year = years.filtered(lambda y: match and y.start_date.year == int(match.group())) if match else years.browse()
        semester = env['umti.academic.term']
        if not reason and len(year) != 1:
            reason = 'academic year %r does not match exactly one year' % ex.get('academic_year')
        if not reason:
            terms = env['umti.academic.term'].search(
                [('academic_year_id', '=', year.id)], order='term_start_date, id')
            idx = SEMESTER_INDEX.get(ex.get('semester'))
            if idx is None or idx >= len(terms):
                reason = 'semester %r has no matching term in %s' % (ex.get('semester'), year.name)
            else:
                semester = terms[idx]
        if not reason and ex['exam_type'] not in TYPE_MAP:
            reason = 'unknown exam type %r' % ex['exam_type']
        if not reason and ex['state'] not in STATE_MAP:
            reason = 'unknown state %r' % ex['state']
        start, end = ex.get('start_time') or 0.0, ex.get('end_time') or 0.0
        defaulted = False
        if not reason:
            if start == 0.0 and end == 0.0:
                start, end, defaulted = 8.0, 10.0, True
            elif not (0 <= start < end < 24):
                reason = 'end time %.2f is not after start time %.2f' % (end, start)
        if not reason and not env['umti.course'].browse(ex['course_id']).exists():
            reason = 'course missing'
        if not reason and ex['unit_id'] not in env['umti.course'].browse(ex['course_id']).unit_ids.ids:
            reason = 'unit is not part of the course'
        if reason:
            skipped[ex['id']] = reason
            _row(report, 'exam', ex['id'], code, 'SKIPPED', reason)
            continue
        plan[ex['id']] = dict(
            name=ex['name'], code=code, course_id=ex['course_id'], unit_id=ex['unit_id'],
            academic_year_id=year.id, semester_id=semester.id,
            date=ex.get('exam_date'), start_time=start, end_time=end,
            assessment_type=TYPE_MAP[ex['exam_type']], max_marks=ex['max_marks'] or 100.0,
            pass_marks=ex['pass_marks'], state=STATE_MAP[ex['state']], company_id=ex['company_id'],
            active=ex['active'], weight=0.0, _times_defaulted=defaulted)

    # a second non-cancelled Final Exam per (course, unit, semester): keep the earliest
    finals = defaultdict(list)
    for eid, v in plan.items():
        if v['assessment_type'] == 'final' and v['state'] != 'cancelled':
            finals[(v['course_id'], v['unit_id'], v['semester_id'])].append(eid)
    for ids in finals.values():
        ids.sort(key=lambda i: (plan[i]['date'] is None, plan[i]['date'], i))
        for eid in ids[1:]:
            reason = 'second Final Exam for the same course/unit/semester (earliest kept)'
            skipped[eid] = reason
            _row(report, 'exam', eid, plan[eid]['code'], 'SKIPPED', reason)
            del plan[eid]

    # equal weights per (unit, semester) for the non-cancelled ones
    groups = defaultdict(list)
    for eid, v in plan.items():
        if v['state'] != 'cancelled':
            groups[(v['unit_id'], v['semester_id'])].append(eid)
    for ids in groups.values():
        share = round(100.0 / len(ids), 6)
        for eid in ids:
            plan[eid]['weight'] = share
        plan[ids[-1]]['weight'] = round(100.0 - share * (len(ids) - 1), 6)

    # --- create assessments -----------------------------------------------------
    created = {}
    for eid, vals in plan.items():
        vals = dict(vals)
        defaulted = vals.pop('_times_defaulted')
        try:
            with cr.savepoint():
                rec = Assessment.create(vals)
        except (ValidationError, UserError) as e:
            skipped[eid] = str(e)
            _row(report, 'exam', eid, vals['code'], 'SKIPPED', str(e))
            continue
        created[eid] = rec
        notes = ['weights set equally, review'] if rec.state != 'cancelled' else []
        if defaulted:
            notes.append('times were empty, defaulted to 08:00-10:00')
        _row(report, 'exam', eid, rec.code, 'MIGRATED', '; '.join(notes))

    # --- lines -------------------------------------------------------------------
    seen = set()
    new_marks = Mark
    for ln in lines:
        code = next((r['code'] for r in exams if r['id'] == ln['exam_id']), '')
        if ln['exam_id'] not in created:
            _row(report, 'line', ln['id'], code, 'SKIPPED', 'its exam was not migrated')
            continue
        student = env['school.student'].with_context(active_test=False).search(
            [('partner_id', '=', ln['student_id'])], limit=1)
        if not student:
            _row(report, 'line', ln['id'], code, 'SKIPPED', 'partner has no student record')
            continue
        if (ln['exam_id'], student.id) in seen:
            _row(report, 'line', ln['id'], code, 'SKIPPED', 'duplicate student line in the same exam')
            continue
        seen.add((ln['exam_id'], student.id))
        try:
            with cr.savepoint():
                mark = Mark.create({
                    'assessment_id': created[ln['exam_id']].id, 'student_id': student.id,
                    'marks': ln['marks_obtained'] or 0.0, 'marked': True,
                    'remarks': ln.get('remarks'), 'state': ln['state'] or 'draft'})
        except (ValidationError, UserError) as e:
            _row(report, 'line', ln['id'], code, 'SKIPPED', str(e))
            continue
        new_marks |= mark
        _row(report, 'line', ln['id'], code, 'MIGRATED')

    new_marks._consolidate()
    return report


def print_report(report):
    counts = defaultdict(int)
    for r in report:
        counts[(r['kind'], r['action'])] += 1
        print('%-5s %-6s %-14s %-9s %s' % (r['kind'], r['legacy_id'], r['code'], r['action'], r['reason']))
    print(dict(counts))


if 'env' in globals():  # odoo shell
    print_report(migrate(env))
    env.cr.commit()
