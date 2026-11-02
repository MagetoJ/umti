# -*- coding: utf-8 -*-
from odoo import models

from odoo.addons.umti_core.models.umti_dashboard import _kpi

STUDENT = "school.student"
APPLICATION = "school.admission.application"
MOVE = "account.move"

STATE_TONES = {
    "active": "success",
    "graduated": "success",
    "incomplete": "warning",
    "deferred": "warning",
    "suspended": "danger",
    "discontinued": "danger",
}


class UmtiDashboardStudents(models.AbstractModel):
    _name = "umti.dashboard.students"
    _inherit = "umti.dashboard.section"
    _description = "Students Dashboard"

    DASH_TITLE = "Students Dashboard"
    DASH_SUBTITLE = "Enrolment, admissions and fee collection"

    def _build(self, data):
        if not self._has(STUDENT):
            return
        self._student_kpis(data)
        self._fee_kpis(data)
        self._student_charts(data)
        self._student_lists(data)

    # ------------------------------------------------------------------
    def _student_kpis(self, data):
        S, path = STUDENT, "company_id"
        total = self._cnt(S, [("active", "=", True)], path)
        active = self._cnt(S, [("state", "=", "active")], path)
        incomplete = self._cnt(S, [("state", "=", "incomplete")], path)
        graduated = self._cnt(S, [("state", "=", "graduated")], path)
        deferred = self._cnt(S, [("state", "=", "deferred")], path)
        suspended = self._cnt(S, [("state", "=", "suspended")], path)
        sponsored = self._cnt(S, [("state", "=", "active"),
                                  ("fee_status", "=", "sponsored")], path)

        data["kpis"] += [
            _kpi("active", "Active Students", active, "fa-users",
                 "%d on the register" % total, "blue", model=S,
                 domain=self._full(S, [("state", "=", "active")], path)),
            _kpi("incomplete", "Awaiting Activation", incomplete,
                 "fa-user-plus", "incomplete profiles",
                 "amber" if incomplete else "green", model=S,
                 domain=self._full(S, [("state", "=", "incomplete")], path)),
        ]
        if self._has(APPLICATION):
            A = APPLICATION
            pending = self._cnt(
                A, [("state", "in", ("submitted", "review"))], path)
            accepted = self._cnt(A, [("state", "=", "accepted")], path)
            data["kpis"].append(_kpi(
                "applications", "Pending Applications", pending,
                "fa-file-text-o",
                "%d accepted, not yet enrolled" % accepted,
                "amber" if pending else "slate", model=A,
                domain=self._full(
                    A, [("state", "in", ("submitted", "review"))], path)))
        data["kpis"] += [
            _kpi("graduated", "Graduated", graduated, "fa-graduation-cap",
                 "completed their course", "green", model=S,
                 domain=self._full(S, [("state", "=", "graduated")], path)),
            _kpi("at_risk", "Deferred or Suspended", deferred + suspended,
                 "fa-pause-circle-o",
                 "%d deferred · %d suspended" % (deferred, suspended),
                 "red" if suspended else ("amber" if deferred else "green"),
                 model=S,
                 domain=self._full(
                     S, [("state", "in", ("deferred", "suspended"))], path)),
            _kpi("sponsored", "Sponsored", sponsored, "fa-handshake-o",
                 "%d%% of active students" % (
                     round(100.0 * sponsored / active) if active else 0),
                 "violet", model=S,
                 domain=self._full(S, [("state", "=", "active"),
                                       ("fee_status", "=", "sponsored")],
                                   path)),
        ]

    def _invoice_domain(self):
        """Posted tuition invoices raised to students' contacts."""
        students = self.env[STUDENT].search(self._full(
            STUDENT, [("partner_id", "!=", False)], "company_id"))
        partners = students.partner_id.ids
        if not partners:
            return None
        return [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                ("partner_id", "in", partners)]

    def _fee_kpis(self, data):
        if not self._has(MOVE):
            return
        domain = self._invoice_domain()
        if domain is None:
            return
        Move = self.env[MOVE]
        scoped = self._full(MOVE, domain, "company_id")
        rows = Move._read_group(
            scoped, [], ["amount_total:sum", "amount_residual:sum"])
        invoiced, outstanding = (rows[0] if rows else (0, 0))
        invoiced, outstanding = invoiced or 0.0, outstanding or 0.0
        collected = invoiced - outstanding
        data["kpis"] += [
            _kpi("fees_collected", "Fees Collected", self._fmt(collected),
                 "fa-money",
                 "%d%% of %s invoiced" % (
                     round(100.0 * collected / invoiced) if invoiced else 0,
                     self._fmt(invoiced)),
                 "green", model=MOVE,
                 domain=scoped + [("payment_state", "in",
                                   ("paid", "in_payment", "partial"))]),
            _kpi("fees_outstanding", "Fees Outstanding",
                 self._fmt(outstanding), "fa-exclamation-circle",
                 "%s still to collect" % self._fmt(outstanding),
                 "red" if outstanding else "green", model=MOVE,
                 domain=scoped + [("payment_state", "in",
                                   ("not_paid", "partial", "blocked"))]),
        ]

    # ------------------------------------------------------------------
    def _student_charts(self, data):
        S, path = STUDENT, "company_id"
        self._chart(data, "state", "Students by status", "bars",
                    self._sel_items(S, "state", None, path))
        items, more = self._group_items(
            S, "course_id", [("course_id", "!=", False)], path)
        self._chart(data, "course", "Students per course", "bars",
                    items, more)
        items, more = self._group_items(
            S, "department_id", [("department_id", "!=", False)], path)
        self._chart(data, "department", "Students per department", "bars",
                    items, more)
        self._chart(data, "admissions", "New students, last 6 months",
                    "bars", self._month_items(S, "create_date", None, path))
        self._chart(data, "gender", "Gender", "donut",
                    self._sel_items(S, "gender", [("state", "=", "active")],
                                    path))
        self._chart(data, "sponsorship", "Who pays the fees", "donut",
                    self._sel_items(S, "fee_status",
                                    [("state", "=", "active")], path))
        if self._has(APPLICATION):
            self._chart(data, "applications", "Applications", "donut",
                        self._sel_items(APPLICATION, "state", None, path))
        if self._has(MOVE):
            domain = self._invoice_domain()
            if domain is not None:
                self._chart(data, "invoices", "Invoice payment status",
                            "donut",
                            self._sel_items(MOVE, "payment_state", domain,
                                            "company_id"))

    # ------------------------------------------------------------------
    def _student_lists(self, data):
        S, path = STUDENT, "company_id"
        Student = self.env[S]
        state_labels = dict(Student._fields["state"].selection)

        if self._has(APPLICATION):
            Application = self.env[APPLICATION]
            labels = dict(Application._fields["state"].selection)
            waiting = Application.search(self._full(
                APPLICATION, [("state", "in", ("submitted", "review"))],
                path), order="id desc", limit=6)
            self._list(data, "waiting", "Applications awaiting review", [
                self._row(app.applicant_name or app.name,
                          " · ".join(p for p in (
                              app.name, app.course_id.name) if p),
                          labels.get(app.state, ""), "warning",
                          APPLICATION, app.id)
                for app in waiting])

        recent = Student.search(
            self._full(S, [("active", "=", True)], path),
            order="create_date desc, id desc", limit=6)
        self._list(data, "recent", "Recently added students", [
            self._row(student.name or student.admission_no,
                      " · ".join(p for p in (
                          student.admission_no, student.course_id.name) if p),
                      state_labels.get(student.state, ""),
                      STATE_TONES.get(student.state, ""), S, student.id)
            for student in recent])

        if self._has(MOVE):
            domain = self._invoice_domain()
            if domain is not None:
                rows = self.env[MOVE]._read_group(
                    self._full(MOVE, domain + [("amount_residual", ">", 0)],
                               "company_id"),
                    ["partner_id"], ["amount_residual:sum"],
                    order="amount_residual:sum desc", limit=5)
                owing = []
                for partner, amount in rows:
                    student = Student.search(
                        [("partner_id", "=", partner.id)], limit=1)
                    owing.append(self._row(
                        student.name or partner.display_name,
                        " · ".join(p for p in (
                            student.admission_no, student.course_id.name)
                            if p),
                        self._fmt(amount), "danger",
                        S if student else None, student.id or None))
                self._list(data, "owing", "Largest fee balances", owing)
