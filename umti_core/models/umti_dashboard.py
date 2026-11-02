# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


def _kpi(key, label, value, icon="fa-bar-chart", hint="", accent="blue",
         model=None, domain=None, view_mode="list,form", res_id=None):
    return {
        "key": key,
        "label": label,
        "value": value,
        "icon": icon,
        "hint": hint,
        "accent": accent,
        # Drill-down target (None when the metric has no single record set).
        "model": model,
        "domain": list(domain or []),
        "view_mode": view_mode,
        "res_id": res_id,
    }


class UmtiDashboard(models.AbstractModel):
    """Aggregated school statistics for the OWL dashboard.

    ``umti_core`` only depends on ``base``/``mail``, so every section is
    guarded: a stat is reported when its model is installed, skipped when it
    is not. Keeping the aggregation here (instead of the controller) makes it
    callable from tests and from server actions.
    """

    _name = "umti.dashboard"
    _description = "School Dashboard Metrics"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _has(self, *model_names):
        return all(name in self.env for name in model_names)

    def _company_domain(self, model_name, path="company_id"):
        """Restrict a domain to the companies picked in the switcher."""
        if model_name not in self.env:
            return []
        return [(path, "in", self.env.companies.ids)]

    def _can_manage_terms(self):
        """Mirrors the write ACL of ``umti.academic.term`` (admin implies
        manager, so this single group covers both)."""
        return self.env.user.has_group(
            "umti_core.group_umti_academic_year_manager")

    def _count(self, model_name, domain=None, path="company_id"):
        if model_name not in self.env:
            return 0
        full_domain = self._company_domain(model_name, path) + list(domain or [])
        return self.env[model_name].search_count(full_domain)

    def _drill(self, model_name, domain=None, path="company_id"):
        """Company-scoped domain for a KPI drill-down."""
        return self._company_domain(model_name, path) + list(domain or [])

    def _selection_items(self, model_name, field_name, domain=None):
        """[{label, value}] for a selection field, zero values dropped."""
        if model_name not in self.env:
            return []
        Model = self.env[model_name]
        base_domain = self._company_domain(model_name) + list(domain or [])
        selection = Model._fields[field_name].selection
        items = []
        for key, label in selection:
            item_domain = base_domain + [(field_name, "=", key)]
            count = Model.search_count(item_domain)
            if count:
                items.append({
                    "label": label,
                    "value": count,
                    "model": model_name,
                    "domain": item_domain,
                })
        return items

    def _action(self, model_name, name, domain=None, view_mode="list,form",
                res_id=None):
        """Client-ready act_window (``views`` is mandatory in Odoo 18)."""
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model_name,
            "view_mode": view_mode,
            "views": [[False, view_type]
                      for view_type in view_mode.split(",")],
            "domain": list(domain or []),
            "res_id": res_id,
            "target": "current",
        }

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self):
        data = {
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "company": {
                "id": self.env.company.id,
                "name": self.env.company.name,
                "currency": self.env.company.currency_id.symbol or "",
                "multi": len(self.env.companies) > 1,
            },
            "kpis": [],
            "charts": [],
            "lists": [],
            "onboarding": None,
        }
        for section in (
            self._onboarding,
            self._term_status,
            self._students,
            self._academics,
            self._admissions,
            self._trainers,
            self._unit_trainers,
            self._enrollments,
            self._attendance,
            self._exams,
            self._fees,
            self._library_and_kits,
            self._recent_activity,
        ):
            section(data)
        return data

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------
    #: Installing the module is itself a setup step, so the bar never starts
    #: empty — 10% is already earned before anything is configured.
    ONBOARDING_BASE = 10

    def _step(self, key, label, hint, done, cta=None, action=None,
              remedy=None, remedy_id=None):
        """One row of the onboarding checklist.

        ``action`` opens records, ``remedy`` runs a server-side fix-up (only
        offered when the current user is allowed to perform it).
        """
        return {
            "key": key,
            "label": label,
            "hint": hint,
            "done": bool(done),
            "cta": None if done else cta,
            "action": None if done else action,
            "remedy": None if done else remedy,
            "remedy_id": None if done else remedy_id,
        }

    def _onboarding(self, data):
        """Guided setup: what still blocks the school from operating.

        Ordered the way a school is actually configured: the calendar, then
        the academic structure, then the org chart, then the people — staff
        before the students they will teach.
        """
        steps = []
        year_ready = True
        today = fields.Date.context_today(self)
        can_write = self._can_manage_terms()

        if self._has("umti.academic.year"):
            Year = self.env["umti.academic.year"]
            years = Year.search(self._company_domain("umti.academic.year"))
            running = years.filtered(lambda y: y.status == "running")
            covering = running.filtered(
                lambda y: y.start_date and y.end_date
                and y.start_date <= today <= y.end_date)
            runnable = covering.filtered(lambda y: y.academic_term_ids)
            year_ready = bool(runnable)
            if runnable:
                year = runnable[0]
                steps.append(self._step(
                    "academic_year", "Academic year",
                    "%s runs to %s · %d semesters generated." % (
                        year.name, fields.Date.to_string(year.end_date),
                        len(year.academic_term_ids)),
                    True))
            elif not years:
                steps.append(self._step(
                    "academic_year", "Academic year",
                    "Create the academic year — its semesters are generated "
                    "for you. Nothing can be recorded before this exists.",
                    False, "Create academic year",
                    self._action("umti.academic.year", _("New Academic Year"),
                                 view_mode="form")))
            else:
                year = covering[0] if covering else (
                    running[0] if running else
                    (years.filtered(lambda y: y.status == "draft") or years)[0])
                remedy = "activate_academic_year"
                if running and not covering:
                    hint = (
                        "The running year %s covers %s to %s, so today falls "
                        "outside it." % (
                            year.name,
                            fields.Date.to_string(year.start_date),
                            fields.Date.to_string(year.end_date)))
                    cta = "Adjust year dates"
                    remedy = None
                elif running and not year.academic_term_ids:
                    hint = (
                        "%s has no semesters yet. Generating them splits the "
                        "year and starts the first semester." % year.name)
                    cta = "Generate semesters"
                else:
                    hint = (
                        "%s is not running yet. Activating it generates the "
                        "semesters and starts the first semester." % year.name)
                    cta = "Activate %s" % year.name
                if remedy and not can_write:
                    # Read-only users still get a way in, just not the action.
                    remedy, cta = None, "Review %s" % year.name
                steps.append(self._step(
                    "academic_year", "Academic year", hint, False, cta,
                    self._action("umti.academic.year", _("Academic Year"),
                                 [("id", "=", year.id)],
                                 view_mode="form", res_id=year.id),
                    remedy=remedy, remedy_id=year.id))

        if self._has("umti.course.level"):
            levels = self._count("umti.course.level", [("active", "=", True)])
            steps.append(self._step(
                "course_levels", "Course levels",
                "%d level(s) defined." % levels if levels else
                "Award levels such as Certificate, Diploma and Degree — "
                "every course is filed under one.",
                levels > 0, "Add course level",
                self._action("umti.course.level", _("Course Levels"),
                             self._drill("umti.course.level",
                                         [("active", "=", True)]))))

        # Departments come before courses: every course is owned by one.
        if self._has("umti.department"):
            Department = self.env["umti.department"]
            departments = Department.search(
                self._company_domain("umti.department")
                + [("active", "=", True)])
            # Head of Department lives in umti_trainers, so it may be absent.
            has_hod = "manager_id" in Department._fields
            without_hod = departments.filtered(
                lambda dept: not dept.manager_id) if has_hod \
                else Department.browse()
            if not departments:
                hint = ("Departments own courses and the trainers who teach "
                        "them.")
                done = False
            elif without_hod:
                hint = "%d department(s) — %d with no Head of Department." % (
                    len(departments), len(without_hod))
                done = False
            else:
                hint = ("%d department(s)%s." % (
                    len(departments),
                    ", each with a Head of Department" if has_hod else ""))
                done = True
            steps.append(self._step(
                "departments", "Departments", hint, done,
                "Add department" if not departments else "Assign heads",
                self._action("umti.department", _("Departments"),
                             self._drill("umti.department",
                                         [("active", "=", True)]))))

        if self._has("umti.course"):
            Course = self.env["umti.course"]
            courses = Course.search(
                self._company_domain("umti.course") + [("active", "=", True)])
            if not courses:
                hint, done = (
                    "Every student enrols into a course. Add one, then attach "
                    "its units, requirements and documents.", False)
            else:
                missing_docs = courses.filtered(
                    lambda c: not c.document_ids)
                missing_quals = courses.filtered(
                    lambda c: not c.qualifying_requirement_ids)
                no_units = courses.filtered(lambda c: not c.unit_ids)
                mismatch = (courses - no_units).filtered(
                    lambda c: c.unit_credit_totals != c.minimum_credits)
                issues = []
                if missing_docs:
                    issues.append("%d with no required documents"
                                  % len(missing_docs))
                if missing_quals:
                    issues.append("%d with no mandatory qualifications"
                                  % len(missing_quals))
                if no_units:
                    issues.append("%d with no units" % len(no_units))
                if mismatch:
                    if len(courses) == 1:
                        issues.append(
                            "unit credits total %d against a minimum of %d"
                            % (mismatch.unit_credit_totals,
                               mismatch.minimum_credits))
                    else:
                        issues.append(
                            "%d whose unit credits do not total their minimum"
                            % len(mismatch))
                if issues:
                    hint = "%d course(s) set up — %s." % (
                        len(courses), ", ".join(issues))
                    done = False
                else:
                    hint = ("%d course(s), fully configured with units, "
                            "documents and requirements." % len(courses))
                    done = True
            steps.append(self._step(
                "courses", "Courses", hint, done,
                "Review courses" if courses else "Add course",
                self._action("umti.course", _("Courses"),
                             self._drill("umti.course",
                                         [("active", "=", True)]))))

        if self._has("umti.fee.structure"):
            approved = self._count(
                "umti.fee.structure", [("status", "=", "approved")])
            drafts = self._count(
                "umti.fee.structure", [("status", "=", "draft")])
            if approved:
                hint = "%d approved structure(s)." % approved
            elif drafts:
                hint = ("%d structure(s) are still draft — approve them "
                        "before invoicing." % drafts)
            else:
                hint = "Define what each course charges, per semester."
            steps.append(self._step(
                "fee_structures", "Fee structures", hint, approved > 0,
                "Review fee structures",
                self._action("umti.fee.structure", _("Fee Structures"),
                             self._drill("umti.fee.structure"))))

        if self._has("umti.trainer.allocation"):
            approved = self._count(
                "umti.trainer.allocation", [("state", "=", "approved")])
            pending = self._count(
                "umti.trainer.allocation", [("state", "=", "draft")])
            if approved:
                hint = "%d trainer(s) approved." % approved
            elif pending:
                hint = ("%d allocation(s) are waiting for approval — "
                        "approving one creates the HR employee and contract."
                        % pending)
            else:
                hint = ("No trainers yet. Allocating one creates their HR "
                        "employee, contract and portal access on approval.")
            steps.append(self._step(
                "trainers", "Trainers", hint, approved > 0, "Manage trainers",
                self._action("umti.trainer.allocation", _("Trainers"),
                             self._drill("umti.trainer.allocation"))))

        # Last: everything above must exist before an intake can be taken.
        if self._has("school.student"):
            students = self._count("school.student", [("active", "=", True)])
            if students:
                hint = "%d student(s) enrolled." % students
                action = self._action("school.student", _("Students"),
                                      self._drill("school.student"))
                cta = "Open students"
            else:
                hint = ("No students yet. Open an intake, take applications "
                        "and admit them into the running semester.")
                action = self._action(
                    "school.admission.intake", _("Intakes"),
                    self._drill("school.admission.intake"))
                cta = "Open intake"
            steps.append(self._step(
                "students", "Students", hint, students > 0, cta, action))

        if not steps:
            return
        done = len([step for step in steps if step["done"]])
        total = len(steps)
        percent = self.ONBOARDING_BASE + int(round(
            (100 - self.ONBOARDING_BASE) * done / total))
        data["onboarding"] = {
            "steps": [dict(step, index=index + 1)
                      for index, step in enumerate(steps)],
            "done": done,
            "total": total,
            "percent": min(100, percent),
            "complete": done == total,
            # The term banner is redundant while the calendar is missing.
            "year_ready": year_ready,
        }

    def _term_info(self, term, status_labels):
        if not term:
            return None
        return {
            "id": term.id,
            "name": term.name,
            "status": term.status,
            "status_label": status_labels.get(term.status, term.status),
            "start": fields.Date.to_string(term.term_start_date),
            "end": fields.Date.to_string(term.term_end_date),
            "academic_year": term.academic_year_id.name or "",
        }

    def _term_status(self, data):
        """Is today inside a semester, and is that semester the running one?"""
        if not self._has("umti.academic.term"):
            return
        Term = self.env["umti.academic.term"]
        today = fields.Date.context_today(self)
        company_domain = self._company_domain("umti.academic.term")
        current = Term.search(company_domain + [
            ("parent_term", "=", False),
            ("term_start_date", "<=", today),
            ("term_end_date", ">=", today),
        ], order="term_start_date desc", limit=1)
        next_term = Term.search(company_domain + [
            ("parent_term", "=", False),
            ("status", "=", "draft"),
            ("term_end_date", ">=", today),
        ], order="term_start_date asc", limit=1)
        if not next_term:
            next_term = Term.search(company_domain + [
                ("parent_term", "=", False),
                ("status", "=", "draft"),
            ], order="term_start_date asc", limit=1)

        status_labels = dict(Term._fields["status"].selection)
        can_write = self._can_manage_terms()
        info = {
            "today": fields.Date.to_string(today),
            "ok": False,
            "reason": "",
            "message": "",
            "current": self._term_info(current, status_labels),
            "next": self._term_info(next_term, status_labels),
            "can_edit": bool(current or next_term) and can_write,
            "can_open_next": bool(next_term) and can_write,
            # The onboarding panel already explains a missing calendar.
            "suppressed": bool(
                data.get("onboarding")
                and not data["onboarding"]["year_ready"]),
        }
        if current and current.status == "in_progress":
            info["ok"] = True
            info["message"] = "%s is in progress until %s." % (
                current.name, fields.Date.to_string(current.term_end_date))
        elif current:
            info["reason"] = "not_in_progress"
            info["message"] = (
                "Today falls in %(term)s, but that semester is %(status)s. "
                "Nothing can be recorded until it is started." % {
                    "term": current.name,
                    "status": status_labels.get(current.status, current.status),
                })
        else:
            info["reason"] = "outside_terms"
            info["message"] = (
                "Today is not inside any semester. Start the next semester "
                "or adjust the semester dates.")
        data["term"] = info

        if current:
            hint = "%s \u00b7 %s to %s" % (
                info["current"]["status_label"],
                info["current"]["start"],
                info["current"]["end"])
            term_name = current.name
        elif next_term:
            hint = "next: %s from %s" % (
                next_term.name,
                fields.Date.to_string(next_term.term_start_date))
            term_name = _("No Term")
        else:
            hint = "no term scheduled"
            term_name = _("No Term")
        data["kpis"].append(_kpi(
            "current_term", "Semester", term_name,
            "fa-calendar-check-o", hint,
            "green" if info["ok"] else ("red" if current else "amber"),
            model="umti.academic.term",
            domain=[("id", "=", current.id if current else
                     (next_term.id if next_term else 0))],
            res_id=current.id if current else (next_term.id if next_term else None)))

    @api.model
    def onboard_academic_year(self, year_id=None):
        """Set the calendar up from the dashboard.

        Generates the semesters of the year when they are missing, starts
        the first term and flags the year as running.
        """
        Year = self.env["umti.academic.year"]
        if not self._can_manage_terms():
            raise AccessError(
                _("You are not allowed to activate an academic year."))
        year = Year.browse(year_id).exists() if year_id else Year.browse()
        if not year:
            raise UserError(_("Choose an academic year to activate first."))
        year.activate_academic_year()
        return {
            "id": year.id,
            "name": year.name,
            "terms": len(year.academic_term_ids),
        }

    @api.model
    def open_next_term(self):
        """Start the next draft term.

        Deliberately does not enrol the student base: units are filled per
        student when their own semester starts, and the trainers cron walks
        the students in batches.
        """
        Term = self.env["umti.academic.term"]
        if not self._can_manage_terms():
            raise AccessError(
                _("You are not allowed to open an semester."))
        today = fields.Date.context_today(self)
        domain = self._company_domain("umti.academic.term") + [
            ("parent_term", "=", False),
            ("status", "=", "draft"),
        ]
        term = Term.search(
            domain + [("term_end_date", ">=", today)],
            order="term_start_date asc", limit=1)
        if not term:
            term = Term.search(domain, order="term_start_date asc", limit=1)
        if not term:
            raise UserError(_("There is no draft term left to open."))
        term.action_activate_academic_term()
        return {"id": term.id, "name": term.name}

    def _students(self, data):
        if not self._has("school.student"):
            return
        active = self._count("school.student", [("state", "=", "active")])
        total = self._count("school.student", [("active", "=", True)])
        incomplete = self._count(
            "school.student", [("state", "=", "incomplete")])
        data["kpis"].append(_kpi(
            "students_active", "Active Students", active, "fa-users",
            "%d enrolled in total" % total, "blue",
            model="school.student",
            domain=self._drill("school.student", [("state", "=", "active")])))
        data["kpis"].append(_kpi(
            "students_pending", "Awaiting Activation", incomplete, "fa-user-clock",
            "incomplete profiles", "amber",
            model="school.student",
            domain=self._drill(
                "school.student", [("state", "=", "incomplete")])))
        data["charts"].append({
            "key": "students_state",
            "title": "Students by status",
            "type": "bars",
            "items": self._selection_items("school.student", "state"),
        })
        courses = []
        if self._has("umti.course"):
            for course in self.env["umti.course"].search(
                    self._company_domain("umti.course")):
                count = self._count(
                    "school.student", [("course_id", "=", course.id)])
                if count:
                    courses.append({
                        "label": course.name or "N/A",
                        "value": count,
                        "model": "school.student",
                        "domain": self._drill(
                            "school.student", [("course_id", "=", course.id)]),
                    })
            courses.sort(key=lambda item: -item["value"])
        data["charts"].append({
            "key": "students_course",
            "title": "Students per course",
            "type": "bars",
            "items": courses[:6],
            "more": max(0, len(courses) - 6),
        })

    def _academics(self, data):
        data["kpis"].append(_kpi(
            "courses", "Courses",
            self._count("umti.course", [("active", "=", True)]),
            "fa-graduation-cap", "active courses", "violet",
            model="umti.course",
            domain=self._drill("umti.course", [("active", "=", True)])))
        data["kpis"].append(_kpi(
            "units", "Units",
            self._count("umti.course.units", [("active", "=", True)]),
            "fa-book", "active units", "green",
            model="umti.course.units",
            domain=self._drill(
                "umti.course.units", [("active", "=", True)])))
        data["kpis"].append(_kpi(
            "departments", "Departments",
            self._count("umti.department", [("active", "=", True)]),
            "fa-building-o", "academic departments", "slate",
            model="umti.department",
            domain=self._drill(
                "umti.department", [("active", "=", True)])))

    def _admissions(self, data):
        if not self._has("school.admission.application"):
            return
        data["kpis"].append(_kpi(
            "applications", "Applications",
            self._count("school.admission.application"),
            "fa-file-text-o", "all intakes", "amber",
            model="school.admission.application",
            domain=self._drill("school.admission.application")))
        data["charts"].append({
            "key": "applications_state",
            "title": "Admission applications",
            "type": "bars",
            "items": self._selection_items(
                "school.admission.application", "state"),
        })

    def _trainers(self, data):
        if not self._has("umti.trainer.allocation"):
            return
        approved = self._count(
            "umti.trainer.allocation", [("state", "=", "approved")])
        pending = self._count(
            "umti.trainer.allocation", [("state", "=", "draft")])
        retired = self._count(
            "umti.trainer.allocation", [("state", "=", "retired")])
        data["kpis"].append(_kpi(
            "trainers", "Trainers", approved, "fa-id-badge",
            "%d awaiting approval" % pending, "green",
            model="umti.trainer.allocation",
            domain=self._drill(
                "umti.trainer.allocation", [("state", "=", "approved")])))
        def trainer_item(label, state, value):
            return {
                "label": label,
                "value": value,
                "model": "umti.trainer.allocation",
                "domain": self._drill(
                    "umti.trainer.allocation", [("state", "=", state)]),
            }

        items = [
            trainer_item("Approved", "approved", approved),
            trainer_item("Draft", "draft", pending),
            trainer_item("Retired", "retired", retired),
        ]
        data["charts"].append({
            "key": "trainers_state",
            "title": "Trainers by status",
            "type": "bars",
            "items": [item for item in items if item["value"]],
        })

    def _unit_trainers(self, data):
        """Units of active courses nobody has been assigned to this term.

        A unit counts as covered from either place an assignment can live:
        a ``umti.unit.trainer`` row for the running term (or one of its
        sub-terms), or an approved ``umti.trainer.allocation`` listing the
        unit. Checking only the term-scoped table reported units as unstaffed
        while the Trainers screen clearly showed a trainer on them.
        """
        if not self._has("umti.unit.trainer", "umti.course.units"):
            return
        units = self.env["umti.course.units"].search(
            self._company_domain("umti.course.units")
            + [("active", "=", True)])
        if not units:
            return
        term = self.env["umti.academic.term"].search(
            self._company_domain("umti.academic.term")
            + [("parent_term", "=", False), ("status", "=", "in_progress")],
            limit=1)
        if not term:
            # Nothing can be assigned before a term is running.
            data["kpis"].append(_kpi(
                "units_without_trainer", "Units Without Trainer", len(units),
                "fa-chalkboard-teacher", "no term in progress", "amber"))
            return
        # Year scope, not term scope: a unit assigned to a trainer in any
        # term of the running year is staffed, even if it is not that
        # trainer's turn yet this semester.
        year = term.academic_year_id
        covered = self.env["umti.unit.trainer"].search(
            self._company_domain("umti.unit.trainer")
            + [("academic_year_id", "=", year.id),
               ("trainer_id", "!=", False)]).unit_id
        if self._has("umti.trainer.allocation"):
            covered |= self.env["umti.trainer.allocation"].search(
                self._company_domain("umti.trainer.allocation")
                + [("state", "=", "approved"), ("active", "=", True)]).unit_ids
        missing = units - covered
        data["kpis"].append(_kpi(
            "units_without_trainer", "Units Without Trainer", len(missing),
            "fa-chalkboard-teacher",
            "%s \u00b7 %d of %d unit(s) covered" % (
                year.name or term.name, len(units & covered), len(units)),
            "red" if missing else "green",
            model="umti.course.units",
            domain=self._drill(
                "umti.course.units", [("id", "in", missing.ids)])))
        if missing:
            data["lists"].append({
                "key": "units_without_trainer",
                "title": "Units without a trainer (%s)"
                         % (year.name or term.name),
                "rows": [{
                    "label": unit.name or unit.code or _("Unit"),
                    "meta": "%s \u00b7 %s credits" % (
                        unit.code or "", unit.credit_contribution or 0),
                    "badge": unit.department_id.name or "",
                } for unit in missing[:5]],
            })

    def _enrollments(self, data):
        if not self._has("umti.student.unit.enrollment"):
            return
        Enrollment = self.env["umti.student.unit.enrollment"]
        enrolled = self._count(
            "umti.student.unit.enrollment", [("state", "=", "enrolled")])
        units = len(Enrollment.search(
            self._company_domain("umti.student.unit.enrollment")
            + [("state", "=", "enrolled")]).mapped("unit_id"))
        without_trainer = self._count(
            "umti.student.unit.enrollment",
            [("state", "=", "enrolled"), ("trainer_id", "=", False)])
        data["kpis"].append(_kpi(
            "enrollments", "Unit Enrollments", enrolled, "fa-list-ol",
            "%d units covered" % units, "violet",
            model="umti.student.unit.enrollment",
            domain=self._drill(
                "umti.student.unit.enrollment", [("state", "=", "enrolled")])))
        data["kpis"].append(_kpi(
            "enrollments_no_trainer", "Without Trainer", without_trainer,
            "fa-user-times", "enrolled students not assigned", "red"
            if without_trainer else "slate",
            model="umti.student.unit.enrollment",
            domain=self._drill("umti.student.unit.enrollment", [
                ("state", "=", "enrolled"), ("trainer_id", "=", False)])))
        data["charts"].append({
            "key": "enrollments_state",
            "title": "Enrollments by state",
            "type": "bars",
            "items": self._selection_items(
                "umti.student.unit.enrollment", "state"),
        })

    def _attendance(self, data):
        if not self._has("umti.attendance.line"):
            return
        submitted = [
            ("sheet_id.state", "=", "done"),
        ]
        present = self._count(
            "umti.attendance.line",
            submitted + [("status_id.is_present", "=", True)],
            path="sheet_id.company_id")
        absent = self._count(
            "umti.attendance.line",
            submitted + [("status_id.is_present", "=", False)],
            path="sheet_id.company_id")
        total = present + absent
        rate = round(100.0 * present / total) if total else 0
        data["kpis"].append(_kpi(
            "attendance_rate", "Attendance", "%d%%" % rate, "fa-check-circle",
            "%d marks recorded" % total, "green" if rate >= 75 else "red",
            model="umti.attendance.sheet",
            domain=self._drill(
                "umti.attendance.sheet", [("state", "=", "done")])))
        data["charts"].append({
            "key": "attendance_split",
            "title": "Attendance (submitted sessions)",
            "type": "donut",
            "items": [
                {
                    "label": "Present",
                    "value": present,
                    "model": "umti.attendance.line",
                    "domain": self._drill(
                        "umti.attendance.line",
                        submitted + [("status_id.is_present", "=", True)],
                        path="sheet_id.company_id"),
                },
                {
                    "label": "Absent",
                    "value": absent,
                    "model": "umti.attendance.line",
                    "domain": self._drill(
                        "umti.attendance.line",
                        submitted + [("status_id.is_present", "=", False)],
                        path="sheet_id.company_id"),
                },
            ],
        })

    def _exams(self, data):
        if not self._has("umti.unit.result"):
            return
        UnitResult = self.env["umti.unit.result"]
        passed = UnitResult.search_count([("result", "=", "pass")])
        failed = UnitResult.search_count([("result", "=", "fail")])
        total = passed + failed
        rate = round(100.0 * passed / total) if total else 0
        data["kpis"].append(_kpi(
            "pass_rate", "Pass Rate", "%d%%" % rate, "fa-graduation-cap",
            "%d units graded" % total, "green" if rate >= 50 else "amber",
            model="umti.unit.result",
            domain=self._drill("umti.unit.result", [("state", "=", "published")])))
        data["charts"].append({
            "key": "results_split",
            "title": "Unit results",
            "type": "donut",
            "items": [
                {
                    "label": "Passed",
                    "value": passed,
                    "model": "umti.unit.result",
                    "domain": self._drill(
                        "umti.unit.result", [("result", "=", "pass")]),
                },
                {
                    "label": "Failed",
                    "value": failed,
                    "model": "umti.unit.result",
                    "domain": self._drill(
                        "umti.unit.result", [("result", "=", "fail")]),
                },
            ],
        })

    def _fees(self, data):
        if not self._has("account.move", "school.student"):
            return
        partners = self.env["school.student"].search(
            self._company_domain("school.student")
            + [("partner_id", "!=", False)]).partner_id.ids
        if not partners:
            return
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("partner_id", "in", partners),
        ] + self._company_domain("account.move")
        groups = self.env["account.move"].read_group(
            domain, ["amount_total:sum", "amount_residual:sum"], [])
        totals = groups[0] if groups else {}
        invoiced = totals.get("amount_total", 0.0) or 0.0
        outstanding = totals.get("amount_residual", 0.0) or 0.0
        data["kpis"].append(_kpi(
            "fees_outstanding", "Fees Outstanding",
            "{:,.0f}".format(outstanding), "fa-money",
            "{:,.0f} invoiced".format(invoiced),
            "red" if outstanding else "green",
            model="account.move",
            domain=domain + [
                ("payment_state", "in", ("not_paid", "partial", "blocked")),
            ]))

    def _library_and_kits(self, data):
        overdue = 0
        if self._has("umti.library.lending"):
            overdue += self._count(
                "umti.library.lending", [("state", "=", "overdue")],
                path="student_id.company_id")
        if self._has("umti.kit.issuance"):
            overdue += self._count(
                "umti.kit.issuance", [("state", "=", "overdue")],
                path="student_id.company_id")
        if overdue:
            data["kpis"].append(_kpi(
                "overdue_items", "Overdue Items", overdue, "fa-exclamation-triangle",
                "books and kits not returned", "amber"))

    def _recent_activity(self, data):
        if self._has("school.admission.application"):
            Application = self.env["school.admission.application"]
            states = dict(Application._fields["state"].selection)
            rows = []
            for application in Application.search(
                    self._company_domain("school.admission.application"),
                    limit=5, order="id desc"):
                rows.append({
                    "label": application.applicant_name or application.name,
                    "meta": application.course_id.name or "",
                    "badge": states.get(application.state, application.state),
                })
            if rows:
                data["lists"].append({
                    "key": "recent_applications",
                    "title": "Latest applications",
                    "rows": rows,
                })
        if self._has("umti.student.unit.enrollment"):
            Enrollment = self.env["umti.student.unit.enrollment"]
            rows = []
            for enrollment in Enrollment.search(
                    self._company_domain("umti.student.unit.enrollment"),
                    limit=5, order="id desc"):
                rows.append({
                    "label": enrollment.student_id.name or "",
                    "meta": "%s · %s" % (
                        enrollment.unit_id.name or "",
                        enrollment.academic_term_id.name or ""),
                    "badge": dict(
                        Enrollment._fields["state"].selection).get(
                            enrollment.state, enrollment.state),
                })
            if rows:
                data["lists"].append({
                    "key": "recent_enrollments",
                    "title": "Latest enrollments",
                    "rows": rows,
                })
