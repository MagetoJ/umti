# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models

from odoo.addons.umti_core.models.umti_dashboard import _kpi

KIT = "umti.kits"
ISSUE = "umti.kit.issuance"
ISSUE_PATH = "student_id.company_id"

ISSUE_TONES = {"leased": "warning", "lost": "danger", "returned": "success"}


class UmtiDashboardKits(models.AbstractModel):
    _name = "umti.dashboard.kits"
    _inherit = "umti.dashboard.section"
    _description = "Kits & Equipment Dashboard"

    DASH_TITLE = "Kits & Equipment Dashboard"
    DASH_SUBTITLE = "Stock, issuances and kits not yet returned"

    def _overdue_domain(self):
        return [("state", "=", "leased"), ("due_date", "<", self._today())]

    def _build(self, data):
        if not self._has(KIT, ISSUE):
            return
        self._kit_kpis(data)
        self._kit_charts(data)
        self._kit_lists(data)

    def _kit_kpis(self, data):
        total = self._cnt(KIT)
        available = self._cnt(KIT, [("status", "=", "available")])
        lost = self._cnt(KIT, [("status", "=", "lost")])
        issued = self._cnt(ISSUE, [("state", "=", "leased")], ISSUE_PATH)
        overdue_domain = self._overdue_domain()
        overdue = self._cnt(ISSUE, overdue_domain, ISSUE_PATH)
        returned = self._cnt(ISSUE, [("state", "=", "returned")], ISSUE_PATH)

        rows = self.env[KIT]._read_group(
            [], [], ["purchase_price:sum"])
        stock_value = (rows[0][0] if rows else 0) or 0.0

        data["kpis"] += [
            _kpi("kits", "Kits & Equipment", total, "fa-briefcase",
                 "%d available to issue" % available, "blue", model=KIT,
                 domain=[]),
            _kpi("available", "Available", available, "fa-check-circle-o",
                 "%d%% of stock" % (
                     round(100.0 * available / total) if total else 0),
                 "green", model=KIT,
                 domain=[("status", "=", "available")]),
            _kpi("issued", "Issued Out", issued, "fa-share-square-o",
                 "currently with students", "violet", model=ISSUE,
                 domain=self._full(ISSUE, [("state", "=", "leased")],
                                   ISSUE_PATH)),
            _kpi("overdue", "Overdue Returns", overdue, "fa-clock-o",
                 "past their due date", "red" if overdue else "green",
                 model=ISSUE,
                 domain=self._full(ISSUE, overdue_domain, ISSUE_PATH)),
            _kpi("returned", "Returned", returned, "fa-undo",
                 "issuances closed", "slate", model=ISSUE,
                 domain=self._full(ISSUE, [("state", "=", "returned")],
                                   ISSUE_PATH)),
            _kpi("lost", "Lost Kits", lost, "fa-question-circle-o",
                 "stock value %s" % self._fmt(stock_value),
                 "amber" if lost else "slate", model=KIT,
                 domain=[("status", "=", "lost")]),
        ]

    def _kit_charts(self, data):
        self._chart(data, "kit_status", "Stock status", "donut",
                    self._sel_items(KIT, "status"))
        self._chart(data, "issue_state", "Issuances by state", "donut",
                    self._sel_items(ISSUE, "state", None, ISSUE_PATH))
        self._chart(data, "issues_month", "Issuances, last 6 months", "bars",
                    self._month_items(ISSUE, "borrow_date", None,
                                      ISSUE_PATH))
        items, more = self._group_items(
            ISSUE, "kit_id", [("state", "!=", "draft")], ISSUE_PATH)
        self._chart(data, "popular", "Most issued kits", "bars", items, more)

    def _kit_lists(self, data):
        today = self._today()
        Issue = self.env[ISSUE]

        overdue = Issue.search(
            self._full(ISSUE, self._overdue_domain(), ISSUE_PATH),
            order="due_date asc", limit=6)
        rows = []
        for issue in overdue:
            days = (today - issue.due_date).days if issue.due_date else 0
            rows.append(self._row(
                issue.kit_id.name,
                "%s · due %s" % (issue.student_id.name or "",
                                 issue.due_date or "—"),
                "%d day%s late" % (days, "" if days == 1 else "s"),
                "danger", ISSUE, issue.id))
        self._list(data, "overdue", "Kits not returned on time", rows)

        soon = Issue.search(self._full(ISSUE, [
            ("state", "=", "leased"), ("due_date", ">=", today),
            ("due_date", "<=", today + timedelta(days=7))], ISSUE_PATH),
            order="due_date asc", limit=6)
        self._list(data, "due_soon", "Due back in the next 7 days", [
            self._row(issue.kit_id.name,
                      "%s · due %s" % (issue.student_id.name or "",
                                       issue.due_date),
                      "Due soon", "warning", ISSUE, issue.id)
            for issue in soon])

        labels = dict(Issue._fields["state"].selection)
        latest = Issue.search(
            self._full(ISSUE, [("state", "!=", "draft")], ISSUE_PATH),
            order="borrow_date desc, id desc", limit=6)
        self._list(data, "latest", "Latest issuances", [
            self._row(issue.kit_id.name,
                      "%s · issued %s" % (issue.student_id.name or "",
                                          issue.borrow_date),
                      labels.get(issue.state, ""),
                      ISSUE_TONES.get(issue.state, ""), ISSUE, issue.id)
            for issue in latest])
