import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const DONUT_COLORS = ["#2563eb", "#ef4444", "#f59e0b", "#10b981", "#8b5cf6"];

export class UmtiDashboard extends Component {
    static template = "umti_core.UmtiDashboard";
    // The action service hands every client action the same props; Owl
    // validates them strictly, so they all have to be declared.
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: [Number, Boolean], optional: true },
        className: { type: String, optional: true },
        state: { type: Object, optional: true },
        updateActionState: { type: Function, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            data: null,
            // The setup checklist is a helper, not the dashboard itself.
            onboardOpen: false,
        });
        onWillStart(() => this.load());
    }

    toggleOnboard() {
        this.state.onboardOpen = !this.state.onboardOpen;
    }

    onOnboardKeydown(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.toggleOnboard();
        }
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = this.section
                ? await rpc("/umti/dashboard/section_data", {
                      section: this.section,
                  })
                : await rpc("/umti/dashboard/data");
        } catch (error) {
            this.state.error =
                (error && (error.data && error.data.message || error.message)) ||
                _t("The dashboard could not be loaded.");
        } finally {
            this.state.loading = false;
        }
    }

    // An area dashboard (students, library, ...) is the same component
    // pointed at another endpoint: its client action carries the section in
    // its context. The main dashboard has none.
    get section() {
        const action = this.props.action || {};
        return (
            (action.context && action.context.umti_section) ||
            (action.params && action.params.section) ||
            null
        );
    }

    get title() {
        const data = this.state.data;
        if (data && data.title) {
            return data.title;
        }
        return data && data.company
            ? _t("%s Dashboard", data.company.name)
            : _t("Dashboard");
    }

    get subtitle() {
        return (this.state.data && this.state.data.subtitle) || "";
    }

    get kpis() {
        return (this.state.data && this.state.data.kpis) || [];
    }

    get charts() {
        return ((this.state.data && this.state.data.charts) || []).filter(
            (chart) => chart.items && chart.items.some((item) => item.value)
        );
    }

    get lists() {
        return (this.state.data && this.state.data.lists) || [];
    }

    get term() {
        return (this.state.data && this.state.data.term) || null;
    }

    get onboarding() {
        return (this.state.data && this.state.data.onboarding) || null;
    }

    errorMessage(error, fallback) {
        return (
            (error && (error.data && error.data.message || error.message)) ||
            fallback
        );
    }

    async runStep(step) {
        if (!step || step.done) {
            return;
        }
        if (step.remedy) {
            try {
                const result = await rpc("/umti/dashboard/onboard", {
                    step: step.remedy,
                    year_id: step.remedy_id,
                });
                this.notification.add(
                    result.terms
                        ? _t(
                              "%s is running with %s semesters.",
                              result.name,
                              result.terms
                          )
                        : _t("%s is now running.", result.name),
                    { type: "success" }
                );
                await this.load();
            } catch (error) {
                this.notification.add(
                    this.errorMessage(
                        error,
                        _t("The academic year could not be set up.")
                    ),
                    { type: "danger" }
                );
            }
            return;
        }
        if (step.action) {
            this.action.doAction(step.action, { onClose: () => this.load() });
        }
    }

    format(value) {
        return typeof value === "number" ? value.toLocaleString() : value;
    }

    openKpi(kpi) {
        if (!kpi.model) {
            return;
        }
        const viewMode = kpi.view_mode || "list,form";
        const action = {
            type: "ir.actions.act_window",
            name: kpi.label,
            res_model: kpi.model,
            domain: kpi.domain || [],
            target: "current",
        };
        if (kpi.res_id) {
            action.res_id = kpi.res_id;
            action.view_mode = "form";
            action.views = [[false, "form"]];
        } else {
            action.view_mode = viewMode;
            action.views = viewMode.split(",").map((type) => [false, type]);
        }
        this.action.doAction(action);
    }

    onKpiKeydown(ev, kpi) {
        if (!kpi.model) {
            return;
        }
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openKpi(kpi);
        }
    }

    openItem(item, name) {
        if (!item || !item.model) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name || item.label,
            res_model: item.model,
            view_mode: "list,form",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: item.domain || [],
            target: "current",
        });
    }

    openRow(row) {
        if (!row || !row.model || !row.res_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: row.model,
            res_id: row.res_id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    editTermDates() {
        const term = this.term;
        const target = term && (term.current || term.next);
        const action = target
            ? {
                  type: "ir.actions.act_window",
                  name: target.name,
                  res_model: "umti.academic.term",
                  res_id: target.id,
                  view_mode: "form",
                  views: [[false, "form"]],
                  target: "current",
              }
            : {
                  type: "ir.actions.act_window",
                  name: _t("Semesters"),
                  res_model: "umti.academic.term",
                  view_mode: "list,form",
                  views: [
                      [false, "list"],
                      [false, "form"],
                  ],
                  target: "current",
              };
        this.action.doAction(action, { onClose: () => this.load() });
    }

    async openNextTerm() {
        try {
            const term = await rpc("/umti/dashboard/open_next_term");
            this.notification.add(
                _t("%s is now in progress.", term.name), { type: "success" }
            );
            await this.load();
        } catch (error) {
            this.notification.add(
                (error && (error.data && error.data.message || error.message)) ||
                    _t("The term could not be opened."),
                { type: "danger" }
            );
        }
    }

    chartTotal(chart) {
        return chart.items.reduce((total, item) => total + item.value, 0);
    }

    barWidth(chart, item) {
        const max = Math.max(...chart.items.map((entry) => entry.value), 1);
        return Math.max(2, Math.round((100 * item.value) / max));
    }

    percent(chart, item) {
        const total = this.chartTotal(chart) || 1;
        return Math.round((100 * item.value) / total);
    }

    donutColor(index) {
        return DONUT_COLORS[index % DONUT_COLORS.length];
    }

    donutStyle(chart) {
        const total = this.chartTotal(chart) || 1;
        let cursor = 0;
        const stops = chart.items.map((item, index) => {
            const start = cursor;
            cursor += (100 * item.value) / total;
            return `${this.donutColor(index)} ${start}% ${cursor}%`;
        });
        return `background: conic-gradient(${stops.join(", ")});`;
    }
}

registry.category("actions").add("umti_dashboard", UmtiDashboard);
registry.category("actions").add("umti_section_dashboard", UmtiDashboard);
