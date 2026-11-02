import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, onMounted } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class StudentDashboard extends Component {
    static template = "umti_students.StudentDashboardTemplate";

    setup() {
        this.rpc = useService("rpc");
        this.deptChartRef = useRef("deptChart");
        this.feeChartRef = useRef("feeChart");
        this.data = {};

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            this.data = await this.rpc("/umti/dashboard/student_data");
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    renderCharts() {
        if (!window.Chart) return;

        // Department Bar Chart
        const deptLabels = this.data.students_by_dept.map(d => d.department_name);
        const deptCounts = this.data.students_by_dept.map(d => d.count);

        new window.Chart(this.deptChartRef.el, {
            type: 'bar',
            data: {
                labels: deptLabels,
                datasets: [{
                    label: 'Students Enrolled',
                    data: deptCounts,
                    backgroundColor: '#1B365D'
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Fee Status Pie Chart
        const feeLabels = this.data.fee_status_breakdown.map(f => f.status.toUpperCase());
        const feeCounts = this.data.fee_status_breakdown.map(f => f.count);

        new window.Chart(this.feeChartRef.el, {
            type: 'pie',
            data: {
                labels: feeLabels,
                datasets: [{
                    data: feeCounts,
                    backgroundColor: ['#28a745', '#ffc107', '#dc3545', '#6c757d']
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }
}

registry.category("actions").add("umti_student_dashboard_action", StudentDashboard);