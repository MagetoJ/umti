# UMTI Students (Odoo 18)

Student management for UMTI. Replaces the former `school_student`,
`school_admission` and `school_portfolio` modules (model names are unchanged).

* Students, guardians, admission documents and the status lifecycle
* Academic years, admission intakes, applications and the review popup (accept / reject)
* Fee records and exam records, shown as tabs on the student form
* Portal page `/my/portfolio`

Depends on `umti_core`.

## Install

    ./odoo-bin -c odoo.conf -d YOUR_DB -i umti_core,umti_students --stop-after-init

Run the tests:

    ./odoo-bin -c odoo.conf -d test_db -i umti_core,umti_students --test-tags /umti_students --stop-after-init

## Security groups

- Student User: create, read, edit students; read courses and departments
- Admission Officer: create and edit applications, read intakes
- Fees and Exams Officer: create and edit fee and exam records
- Student Manager: full access, implies both officer groups

## Status flow

Incomplete -> Active -> Graduated, with Deferred, Suspended and Discontinued
as side states. Activation requires gender, date of birth, mobile, course and
one emergency contact (and a sponsor if the student is sponsored).
