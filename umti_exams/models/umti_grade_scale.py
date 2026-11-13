from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UmtiGradeScale(models.Model):
    _name = "umti.grade.scale"
    _description = "Grade Scale Configuration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Grade Scale Name", required=True, tracking=True)
    code = fields.Char(string="Code / Reference", tracking=True)
    pass_mark = fields.Float(
        string="Pass Mark (%)", default=50.0, required=True, tracking=True
    )
    is_default = fields.Boolean(
        string="Default Scale", default=False, tracking=True
    )

    line_ids = fields.One2many(
        "umti.grade.scale.line",
        "grade_scale_id",
        string="Grade Breakdown Lines",
    )

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    @api.model
    def _get_default(self, company_id=None):
        """Returns the default grade scale record for the specified or current company."""
        company = company_id or self.env.company
        return self.search([
            ("company_id", "=", company.id),
            ("is_default", "=", True)
        ], limit=1)

    @api.constrains("is_default")
    def _check_default_scale(self):
        """Ensure only one scale per company is flagged as default."""
        for rec in self:
            if rec.is_default:
                other_defaults = self.search([
                    ("id", "!=", rec.id),
                    ("company_id", "=", rec.company_id.id),
                    ("is_default", "=", True)
                ])
                if other_defaults:
                    other_defaults.write({"is_default": False})

    def grade_for(self, percentage):
        """Grade letter for a percentage."""
        self.ensure_one()
        return self.get_grade_for_score(percentage)[0]

    def is_pass(self, percentage):
        self.ensure_one()
        return percentage >= self.pass_mark

    def get_grade_for_score(self, score):
        """Returns (grade_letter, result_status, remark) based on percent score."""
        self.ensure_one()
        for line in self.line_ids.sorted(key=lambda l: l.min_mark, reverse=True):
            if score >= line.min_mark:
                return line.grade, line.result_status, line.description
        return "F", "fail", "Below Pass Mark"


class UmtiGradeScaleLine(models.Model):
    _name = "umti.grade.scale.line"
    _description = "Grade Scale Line Item"
    _order = "min_mark desc"

    grade_scale_id = fields.Many2one(
        "umti.grade.scale", string="Grade Scale", ondelete="cascade"
    )
    grade = fields.Char(string="Grade / Key Code", required=True)
    min_mark = fields.Float(string="Min Score (%)", required=True)
    max_mark = fields.Float(string="Max Score (%)", required=True)
    result_status = fields.Selection(
        [("pass", "Pass"), ("fail", "Fail")],
        string="Result Status",
        default="pass",
        required=True,
    )
    description = fields.Char(string="Performance Descriptor / Remarks")

    @api.constrains("min_mark", "max_mark")
    def _check_marks(self):
        for line in self:
            if line.min_mark > line.max_mark:
                raise ValidationError(
                    _("Minimum score cannot be greater than maximum score.")
                )