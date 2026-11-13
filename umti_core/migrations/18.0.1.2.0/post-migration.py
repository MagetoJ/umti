import re

from odoo import SUPERUSER_ID, api

#: The names the old hardcoded admission fields were matched against.
NAME_TO_CODE = {
    "kcse certificate": "kcse",
    "kcpe certificate": "kcpe",
    "leaving certificate": "leaving",
    "national id": "national_id",
    "passport": "passport",
    "birth certificate": "birth_cert",
}


def _slug(name):
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    return slug or "document"


def migrate(cr, version):
    """Give every existing document requirement a stable code.

    Codes used to be implicit: admissions matched the requirement *name*
    against a fixed list of fields. Codes make the link explicit and let new
    documents be added without any code change.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Requirement = env["umti.course.required.documents"]
    taken = {
        (requirement.company_id.id, requirement.code)
        for requirement in Requirement.search([("code", "!=", False)])
    }
    for requirement in Requirement.search([("code", "=", False)]):
        code = NAME_TO_CODE.get((requirement.name or "").strip().lower())
        if not code:
            code = _slug(requirement.name)
            candidate, counter = code, 2
            while (requirement.company_id.id, candidate) in taken:
                candidate = "%s_%s" % (code, counter)
                counter += 1
            code = candidate
        if (requirement.company_id.id, code) in taken:
            # The presets already carry that code; reuse theirs.
            continue
        requirement.write({"code": code})
        taken.add((requirement.company_id.id, code))
