import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class ExamOfficerDashboard extends Component {
    static template = "umti_exams.ExamOfficerDashboard";
    // The action service gives every client action the same props and Owl
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
        this.state = useState({
            loading: true,
            error: null,
            data: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await rpc("/umti/dashboard/exam_officer_data");
        } catch (error) {
            this.state.error =
                (error && ((error.data && error.data.message) || error.message)) ||
                _t("The dashboard could not be loaded.");
        } finally {
            this.state.loading = false;
        }
    }

    /** Share of `part` in `whole`, as a whole-number percentage. */
    percent(part, whole) {
        return whole ? Math.round((100 * part) / whole) : 0;
    }

    /** "62% of 340 results" - the % sign stays outside the translated string. */
    resultShare(part, total) {
        return `${this.percent(part, total)}% ` + _t("of %(total)s results", { total });
    }

    /** Domains come from the server so a tile and its list always agree. */
    domain(key) {
        return (this.state.data && this.state.data.domains[key]) || [];
    }

    get kpis() {
        const { assessments, marks, results } = this.state.data;
        return [
            {
                id: "pending_reviews",
                label: _t("Pending Reviews"),
                value: assessments.pending_review,
                hint: _t("of %(total)s assessments", { total: assessments.total }),
                icon: "fa-hourglass-half",
                tone: "warning",
                open: () =>
                    this.openList(
                        "umti.assessment",
                        _t("Pending Reviews"),
                        this.domain("assessments_pending_review")
                    ),
            },
            {
                id: "marks_pending",
                label: _t("Marks Pending Approval"),
                value: marks.pending,
                hint: _t("of %(total)s marks recorded", { total: marks.total }),
                icon: "fa-pencil-square-o",
                tone: "info",
                open: () =>
                    this.openList(
                        "umti.assessment.mark",
                        _t("Marks Pending Approval"),
                        this.domain("marks_pending")
                    ),
            },
            {
                id: "results_pass",
                label: _t("Passed Unit Results"),
                value: results.pass,
                hint: this.resultShare(results.pass, results.total),
                icon: "fa-check-circle",
                tone: "success",
                open: () =>
                    this.openList(
                        "umti.unit.result",
                        _t("Passed Unit Results"),
                        this.domain("results_pass")
                    ),
            },
            {
                id: "results_fail",
                label: _t("Failed Unit Results"),
                value: results.fail,
                hint: this.resultShare(results.fail, results.total),
                icon: "fa-times-circle",
                tone: "danger",
                open: () =>
                    this.openList(
                        "umti.unit.result",
                        _t("Failed Unit Results"),
                        this.domain("results_fail")
                    ),
            },
        ];
    }

    openList(resModel, name, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            domain,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    openDepartment(dept) {
        this.openList(
            "umti.assessment",
            _t("Assessments — %(department)s", { department: dept.name }),
            dept.domain
        );
    }

    onTileKeydown(ev, callback) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            callback();
        }
    }
}

registry.category("actions").add("action_exam_officer_dashboard", ExamOfficerDashboard);
