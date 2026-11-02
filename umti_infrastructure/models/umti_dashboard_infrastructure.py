# -*- coding: utf-8 -*-
from odoo import models

from odoo.addons.umti_core.models.umti_dashboard import _kpi

FACILITY = "umti.facility"
EQUIPMENT = "umti.facility.equipment"
CLASS = "umti.class.schedule"
EXAM = "umti.exam.schedule"
SLOT = "umti.timetable.slot"

TEACHING_TYPES = ("classroom", "lecture_hall", "lab", "computer_lab",
                  "workshop")
RUNNING = [("academic_term_id.status", "=", "in_progress")]
EXAM_TONES = {"draft": "warning", "confirmed": "", "published": "success"}


class UmtiDashboardInfrastructure(models.AbstractModel):
    _name = "umti.dashboard.infrastructure"
    _inherit = "umti.dashboard.section"
    _description = "Campus Infrastructure Dashboard"

    DASH_TITLE = "Campus Infrastructure Dashboard"
    DASH_SUBTITLE = "Rooms, equipment, timetable load and exams"

    def _build(self, data):
        if not self._has(FACILITY):
            return
        self._campus_kpis(data)
        self._campus_charts(data)
        self._campus_lists(data)

    # ------------------------------------------------------------------
    def _campus_kpis(self, data):
        F, path = FACILITY, "company_id"
        total = self._cnt(F, None, path)
        available = self._cnt(F, [("status", "=", "available")], path)
        maintenance = self._cnt(F, [("status", "=", "maintenance")], path)
        reserved = self._cnt(F, [("status", "=", "reserved")], path)
        rows = self.env[F]._read_group(
            self._full(F, [("status", "=", "available")], path), [],
            ["capacity:sum"])
        seats = (rows[0][0] if rows else 0) or 0
        buildings = len({
            name for name in self.env[F].search(
                self._full(F, None, path)).mapped("building_name") if name})

        data["kpis"] += [
            _kpi("facilities", "Rooms & Facilities", total, "fa-building-o",
                 "%d building%s" % (buildings, "" if buildings == 1 else "s"),
                 "blue", model=F, domain=self._full(F, None, path)),
            _kpi("available", "Available Now", available,
                 "fa-check-circle-o",
                 "%d reserved" % reserved, "green", model=F,
                 domain=self._full(F, [("status", "=", "available")], path)),
            _kpi("maintenance", "Under Maintenance", maintenance, "fa-wrench",
                 "closed for repairs", "amber" if maintenance else "green",
                 model=F,
                 domain=self._full(F, [("status", "=", "maintenance")],
                                   path)),
            _kpi("seats", "Seating Capacity", seats, "fa-users",
                 "across available rooms", "violet"),
        ]

        if self._has(EQUIPMENT):
            E, epath = EQUIPMENT, "facility_id.company_id"
            broken = self._cnt(E, [("condition", "=", "broken")], epath)
            repair = self._cnt(E, [("condition", "=", "repair_needed")],
                               epath)
            data["kpis"].append(_kpi(
                "equipment", "Equipment Needing Attention", broken + repair,
                "fa-exclamation-triangle",
                "%d broken · %d need repair" % (broken, repair),
                "red" if broken else ("amber" if repair else "green"),
                model=E,
                domain=self._full(
                    E, [("condition", "in", ("broken", "repair_needed"))],
                    epath),
                view_mode="list"))

        if self._has(CLASS, SLOT):
            classes = self._cnt(CLASS, RUNNING, "company_id")
            teaching = self._cnt(
                F, [("status", "=", "available"),
                    ("facility_type", "in", TEACHING_TYPES)], path)
            slots = self._cnt(SLOT, [("slot_type", "in", ("regular", "both"))])
            capacity = teaching * slots
            used = len(set(self.env[CLASS].search(
                self._full(CLASS, RUNNING, "company_id")).mapped(
                    lambda rec: (rec.facility_id.id, rec.slot_id.id))))
            data["kpis"] += [
                _kpi("classes", "Classes This Semester", classes,
                     "fa-calendar", "on the running timetable", "blue",
                     model=CLASS,
                     domain=self._full(CLASS, RUNNING, "company_id")),
                _kpi("utilisation", "Room Utilisation",
                     "%d%%" % (round(100.0 * used / capacity)
                               if capacity else 0),
                     "fa-pie-chart",
                     "%d of %d weekly room slots booked" % (used, capacity),
                     "violet"),
            ]

        if self._has(EXAM):
            today = self._today()
            upcoming = self._cnt(EXAM, [("exam_date", ">=", today)],
                                 "company_id")
            unpublished = self._cnt(
                EXAM, [("exam_date", ">=", today),
                       ("status", "!=", "published")], "company_id")
            data["kpis"].append(_kpi(
                "exams", "Upcoming Exams", upcoming, "fa-pencil-square-o",
                "%d not yet published" % unpublished,
                "amber" if unpublished else "green", model=EXAM,
                domain=self._full(EXAM, [("exam_date", ">=", today)],
                                  "company_id")))

    # ------------------------------------------------------------------
    def _campus_charts(self, data):
        F, path = FACILITY, "company_id"
        self._chart(data, "type", "Rooms by type", "bars",
                    self._sel_items(F, "facility_type", None, path))
        self._chart(data, "status", "Room status", "donut",
                    self._sel_items(F, "status", None, path))
        items, more = self._group_items(F, "building_name", None, path)
        self._chart(data, "building", "Rooms per building", "bars",
                    items, more)
        if self._has(EQUIPMENT):
            self._chart(data, "condition", "Equipment condition", "donut",
                        self._sel_items(EQUIPMENT, "condition", None,
                                        "facility_id.company_id"))
        if self._has(CLASS):
            self._chart(data, "days", "Classes per weekday", "bars",
                        self._sel_items(CLASS, "day_of_week", RUNNING,
                                        "company_id"))
            items, more = self._group_items(CLASS, "facility_id", RUNNING,
                                            "company_id")
            self._chart(data, "busiest", "Busiest rooms", "bars",
                        items, more)

    # ------------------------------------------------------------------
    def _campus_lists(self, data):
        F, path = FACILITY, "company_id"
        Facility = self.env[F]
        labels = dict(Facility._fields["status"].selection)

        attention = Facility.search(self._full(F, [
            "|", ("status", "=", "maintenance"),
            ("equipment_ids.condition", "in", ("broken", "repair_needed")),
        ], path), limit=8)
        rows = []
        for room in attention:
            faulty = room.equipment_ids.filtered(
                lambda eq: eq.condition in ("broken", "repair_needed"))
            if room.status == "maintenance":
                badge, tone = labels["maintenance"], "warning"
            else:
                badge, tone = "%d faulty" % len(faulty), "danger"
            rows.append(self._row(
                room.display_name,
                ", ".join(faulty.mapped("name")[:3]) or (room.remarks or ""),
                badge, tone, F, room.id))
        self._list(data, "attention", "Rooms needing attention", rows)

        if self._has(CLASS):
            over = []
            for sched in self.env[CLASS].search(
                    self._full(CLASS, RUNNING, "company_id")):
                extra = sched.student_count - (sched.facility_id.capacity or 0)
                if extra > 0:
                    over.append((extra, sched))
            over.sort(key=lambda pair: -pair[0])
            self._list(data, "over_capacity", "Classes over room capacity", [
                self._row(
                    sched.unit_id.name or sched.display_name,
                    "%s · %s %s · %d students, %d seats" % (
                        sched.facility_id.name, sched.day_label or "",
                        sched.time_range or "", sched.student_count,
                        sched.facility_id.capacity),
                    "+%d" % extra, "danger", CLASS, sched.id)
                for extra, sched in over[:6]])

        if self._has(EXAM):
            Exam = self.env[EXAM]
            status = dict(Exam._fields["status"].selection)
            upcoming = Exam.search(self._full(
                EXAM, [("exam_date", ">=", self._today())], "company_id"),
                order="exam_date asc, id asc", limit=6)
            self._list(data, "exams", "Upcoming exams", [
                self._row(
                    exam.unit_id.name or exam.display_name,
                    "%s · %s · %s" % (exam.exam_date, exam.facility_id.name,
                                      exam.slot_id.display_name or ""),
                    status.get(exam.status, ""),
                    EXAM_TONES.get(exam.status, ""), EXAM, exam.id)
                for exam in upcoming])
