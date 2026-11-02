# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from .umti_dashboard import _kpi  # noqa: F401  (re-exported for sections)


class UmtiDashboardSection(models.AbstractModel):
    """Base for the per-area dashboards (students, library, kits, campus).

    A section is an abstract model named ``umti.dashboard.<key>`` that
    overrides :meth:`_build`. It is rendered by the same OWL component as the
    main dashboard, so it only has to return ``kpis``, ``charts`` and
    ``lists`` in the same shape. Nothing here uses ``sudo``: a section shows
    what the current user is allowed to read.
    """

    _name = "umti.dashboard.section"
    _description = "Dashboard Section Base"

    #: Heading and one-line description shown above the figures.
    DASH_TITLE = "Dashboard"
    DASH_SUBTITLE = ""

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self):
        data = {
            "title": self.DASH_TITLE,
            "subtitle": self.DASH_SUBTITLE,
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
        self._build(data)
        return data

    def _build(self, data):
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------
    def _has(self, *model_names):
        return all(name in self.env for name in model_names)

    def _today(self):
        return fields.Date.context_today(self)

    def _full(self, model_name, domain=None, path=None):
        """``domain`` limited to the companies picked in the switcher.

        ``path`` is the company field on the model (``company_id``) or a
        related path (``student_id.company_id``); models without any company
        link pass ``None`` and are not filtered.
        """
        scope = [(path, "in", self.env.companies.ids)] if path else []
        return scope + list(domain or [])

    def _cnt(self, model_name, domain=None, path=None):
        if model_name not in self.env:
            return 0
        return self.env[model_name].search_count(
            self._full(model_name, domain, path))

    def _fmt(self, amount):
        return "{:,.0f}".format(amount or 0)

    # ------------------------------------------------------------------
    # Chart helpers
    # ------------------------------------------------------------------
    def _item(self, label, value, model, domain):
        return {"label": label, "value": value,
                "model": model, "domain": domain}

    def _sel_items(self, model_name, field_name, domain=None, path=None):
        """One item per selection value that has records."""
        if model_name not in self.env:
            return []
        Model = self.env[model_name]
        base = self._full(model_name, domain, path)
        items = []
        for key, label in Model._fields[field_name].selection:
            item_domain = base + [(field_name, "=", key)]
            count = Model.search_count(item_domain)
            if count:
                items.append(self._item(label, count, model_name,
                                        item_domain))
        return items

    def _group_items(self, model_name, field_name, domain=None, path=None,
                     limit=6):
        """Top groups of a many2one / char field, biggest first.

        Returns ``(items, more)`` where ``more`` is how many groups were cut.
        """
        if model_name not in self.env:
            return [], 0
        Model = self.env[model_name]
        base = self._full(model_name, domain, path)
        rows = Model._read_group(base, [field_name], ["__count"])
        rows = sorted(rows, key=lambda row: -row[1])
        items = []
        for value, count in rows[:limit]:
            if hasattr(value, "display_name"):
                label, match = value.display_name, value.id
            else:
                label, match = value or _("Not set"), value or False
            items.append(self._item(
                label, count, model_name,
                base + [(field_name, "=", match)]))
        return items, max(0, len(rows) - limit)

    def _month_items(self, model_name, date_field, domain=None, path=None,
                     months=6):
        """Records per calendar month for the last ``months`` months."""
        if model_name not in self.env:
            return []
        Model = self.env[model_name]
        first = self._today().replace(day=1) - relativedelta(
            months=months - 1)
        base = self._full(model_name, domain, path)
        items = []
        for index in range(months):
            start = first + relativedelta(months=index)
            end = start + relativedelta(months=1)
            window = base + [(date_field, ">=", start),
                             (date_field, "<", end)]
            items.append(self._item(
                start.strftime("%b %Y"), Model.search_count(window),
                model_name, window))
        return items

    def _chart(self, data, key, title, chart_type, items, more=0):
        data["charts"].append({
            "key": key, "title": title, "type": chart_type,
            "items": items, "more": more,
        })

    def _list(self, data, key, title, rows):
        if rows:
            data["lists"].append({"key": key, "title": title, "rows": rows})

    def _row(self, label, meta="", badge="", tone="", model=None,
             res_id=None):
        return {"label": label, "meta": meta, "badge": badge, "tone": tone,
                "model": model, "res_id": res_id}
