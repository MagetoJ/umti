# -*- coding: utf-8 -*-
import re

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class UmtiDashboardController(http.Controller):

    @http.route("/umti/dashboard/data", type="json", auth="user")
    def dashboard_data(self, **_kwargs):
        """Dashboard payload for the OWL client action.

        Only internal users may read school-wide statistics, regardless of
        the action's menu visibility.
        """
        if not request.env.user.has_group("base.group_user"):
            raise AccessError(_("Only internal users can view the dashboard."))
        return request.env["umti.dashboard"].get_dashboard_data()

    @http.route("/umti/dashboard/onboard", type="json", auth="user")
    def onboard_step(self, step=None, year_id=None, **_kwargs):
        """Run a server-side fix-up offered by the onboarding checklist."""
        if not request.env.user.has_group("base.group_user"):
            raise AccessError(_("Only internal users can set the school up."))
        dashboard = request.env["umti.dashboard"]
        if step == "activate_academic_year":
            return dashboard.onboard_academic_year(year_id)
        raise AccessError(_("Unknown setup step."))

    @http.route("/umti/dashboard/open_next_term", type="json", auth="user")
    def open_next_term(self, **_kwargs):
        """Start the next term from the dashboard warning banner."""
        if not request.env.user.has_group("base.group_user"):
            raise AccessError(_("Only internal users can open a term."))
        return request.env["umti.dashboard"].open_next_term()

    @http.route("/umti/dashboard/section_data", type="json", auth="user")
    def section_data(self, section=None, **_kwargs):
        """Payload for one area dashboard (students, library, kits, ...).

        ``section`` maps to the abstract model ``umti.dashboard.<section>``,
        so installing a module is enough to make its dashboard available.
        """
        if not request.env.user.has_group("base.group_user"):
            raise AccessError(_("Only internal users can view the dashboard."))
        model_name = "umti.dashboard.%s" % (section or "")
        if (not section or not re.fullmatch(r"[a-z_]+", section)
                or model_name not in request.env):
            raise UserError(_("Unknown dashboard."))
        return request.env[model_name].get_dashboard_data()
