# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models

from odoo.addons.umti_core.models.umti_dashboard import _kpi

BOOK = "umti.library.books"
LOAN = "umti.library.lending"
# Lendings and students carry the company; books do not.
LOAN_PATH = "student_id.company_id"

LOAN_TONES = {"leased": "warning", "overdue": "danger", "lost": "danger",
              "returned": "success"}


class UmtiDashboardLibrary(models.AbstractModel):
    _name = "umti.dashboard.library"
    _inherit = "umti.dashboard.section"
    _description = "Library Dashboard"

    DASH_TITLE = "Library Dashboard"
    DASH_SUBTITLE = "Catalogue, loans and overdue books"

    def _overdue_domain(self):
        """Marked overdue, or still out past the due date."""
        return ["|", ("state", "=", "overdue"),
                "&", ("state", "=", "leased"),
                ("due_date", "<", self._today())]

    def _build(self, data):
        if not self._has(BOOK, LOAN):
            return
        self._library_kpis(data)
        self._library_charts(data)
        self._library_lists(data)

    def _library_kpis(self, data):
        titles = self._cnt(BOOK)
        available = self._cnt(BOOK, [("status", "=", "available")])
        lost = self._cnt(BOOK, [("status", "=", "lost")])
        on_loan = self._cnt(LOAN, [("state", "in", ("leased", "overdue"))],
                            LOAN_PATH)
        overdue_domain = self._overdue_domain()
        overdue = self._cnt(LOAN, overdue_domain, LOAN_PATH)

        Loan = self.env[LOAN]
        fined = Loan.search(self._full(
            LOAN, [("overdue_charge_id", "!=", False)], LOAN_PATH))
        fines_due = sum(
            fined.mapped("overdue_charge_id").filtered(
                lambda move: move.state == "posted").mapped(
                    "amount_residual"))

        data["kpis"] += [
            _kpi("titles", "Books in Catalogue", titles, "fa-book",
                 "%d available to borrow" % available, "blue", model=BOOK,
                 domain=[]),
            _kpi("available", "Available", available, "fa-check-circle-o",
                 "%d%% of the catalogue" % (
                     round(100.0 * available / titles) if titles else 0),
                 "green", model=BOOK,
                 domain=[("status", "=", "available")]),
            _kpi("on_loan", "On Loan", on_loan, "fa-exchange",
                 "currently with students", "violet", model=LOAN,
                 domain=self._full(
                     LOAN, [("state", "in", ("leased", "overdue"))],
                     LOAN_PATH)),
            _kpi("overdue", "Overdue", overdue, "fa-clock-o",
                 "past their due date", "red" if overdue else "green",
                 model=LOAN,
                 domain=self._full(LOAN, overdue_domain, LOAN_PATH)),
            _kpi("lost", "Lost Books", lost, "fa-question-circle-o",
                 "written off the catalogue", "amber" if lost else "slate",
                 model=BOOK, domain=[("status", "=", "lost")]),
            _kpi("fines", "Fines Outstanding", self._fmt(fines_due),
                 "fa-money", "%d loans fined" % len(fined),
                 "red" if fines_due else "green", model=LOAN,
                 domain=self._full(
                     LOAN, [("overdue_charge_id", "!=", False)], LOAN_PATH)),
        ]

    def _library_charts(self, data):
        self._chart(data, "book_status", "Catalogue status", "donut",
                    self._sel_items(BOOK, "status"))
        self._chart(data, "loan_state", "Loans by state", "donut",
                    self._sel_items(LOAN, "state", None, LOAN_PATH))
        self._chart(data, "loans_month", "Loans, last 6 months", "bars",
                    self._month_items(LOAN, "borrow_date", None, LOAN_PATH))
        items, more = self._group_items(BOOK, "genre_id")
        self._chart(data, "genre", "Books per genre", "bars", items, more)
        items, more = self._group_items(
            LOAN, "book_id", [("state", "!=", "draft")], LOAN_PATH)
        self._chart(data, "popular", "Most borrowed books", "bars",
                    items, more)

    def _library_lists(self, data):
        today = self._today()
        Loan = self.env[LOAN]

        overdue = Loan.search(
            self._full(LOAN, self._overdue_domain(), LOAN_PATH),
            order="due_date asc", limit=6)
        rows = []
        for loan in overdue:
            days = (today - loan.due_date).days if loan.due_date else 0
            rows.append(self._row(
                loan.book_id.title,
                "%s · due %s" % (loan.student_id.name or "",
                                 loan.due_date or "—"),
                "%d day%s late" % (days, "" if days == 1 else "s"),
                "danger", LOAN, loan.id))
        self._list(data, "overdue", "Overdue books", rows)

        soon = Loan.search(self._full(LOAN, [
            ("state", "=", "leased"), ("due_date", ">=", today),
            ("due_date", "<=", today + timedelta(days=7))], LOAN_PATH),
            order="due_date asc", limit=6)
        self._list(data, "due_soon", "Due in the next 7 days", [
            self._row(loan.book_id.title,
                      "%s · due %s" % (loan.student_id.name or "",
                                       loan.due_date),
                      "Due soon", "warning", LOAN, loan.id)
            for loan in soon])

        labels = dict(Loan._fields["state"].selection)
        latest = Loan.search(
            self._full(LOAN, [("state", "!=", "draft")], LOAN_PATH),
            order="borrow_date desc, id desc", limit=6)
        self._list(data, "latest", "Latest loans", [
            self._row(loan.book_id.title,
                      "%s · borrowed %s" % (loan.student_id.name or "",
                                            loan.borrow_date),
                      labels.get(loan.state, ""),
                      LOAN_TONES.get(loan.state, ""), LOAN, loan.id)
            for loan in latest])

