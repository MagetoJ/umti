import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, onMounted } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class KitsDashboard extends Component {
    static template = "umti_students.KitsDashboardTemplate";

    setup() {
        this.rpc = useService("rpc");
        this.conditionChartRef = useRef("conditionChart");
        this.kitUsageChartRef = useRef("kitUsageChart");
        this.data = {};

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            this.data = await this.rpc("/umti/dashboard/kits_data");
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    renderCharts() {
        if (!window.Chart) return;

        // Condition Chart
        new window.Chart(this.conditionChartRef.el, {
            type: 'doughnut',
            data: {
                labels: ['Good Condition', 'Damaged', 'Lost'],
                datasets: [{
                    data: [
                        this.data.conditions.good,
                        this.data.conditions.damaged,
                        this.data.conditions.lost
                    ],
                    backgroundColor: ['#28a745', '#ffc107', '#dc3545']
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Kit Usage Chart
        const labels = this.data.issuances_by_kit.map(k => k.kit_name);
        const counts = this.data.issuances_by_kit.map(k => k.count);

        new window.Chart(this.kitUsageChartRef.el, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Issuances',
                    data: counts,
                    backgroundColor: '#17a2b8'
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }
}

registry.category("actions").add("umti_kits_dashboard_action", KitsDashboard);