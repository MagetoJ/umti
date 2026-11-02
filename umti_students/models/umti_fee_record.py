# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UmtiFeeRecord(models.Model):
    _name = 'umti.fee.record'
    _description = 'Umti Student Fee Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # --- who / when (links to umti_core, no free text) -------------------
    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        ondelete='cascade', index=True, tracking=True)
    academic_year_id = fields.Many2one(
        'umti.academic.year', string='Academic Year', required=True, tracking=True)
    # same field name umti_core uses on umti.fee.structure.line
    semester_id = fields.Many2one(
        'umti.academic.term', string='Semester', required=True, tracking=True,
        domain="[('academic_year_id', '=', academic_year_id)]")
    course_id = fields.Many2one(
        'umti.course', string='Course', required=True, tracking=True)
    department_id = fields.Many2one(
        'umti.department', string='Department',
        related='course_id.department_id', store=True, readonly=True)
    fee_structure_line_id = fields.Many2one(
        'umti.fee.structure.line', string='Fee Structure Line', tracking=True,
        domain="[('academic_year_id', '=', academic_year_id), "
               "('course_id', '=', course_id), "
               "('semester_id', 'in', [semester_id, False])]")

    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    description = fields.Char(help="e.g. Tuition, Hostel, Library fee")

    # --- amounts -----------------------------------------------------------
    currency_id = fields.Many2one(
        'res.currency', string='Currency', compute='_compute_currency_id',
        store=True, readonly=False)
    fee_amount = fields.Monetary(
        string='Fee Charged', currency_field='currency_id', tracking=True,
        compute='_compute_fee_amount', store=True, readonly=False)
    payment_amount = fields.Monetary(
        string='Amount Paid', currency_field='currency_id', tracking=True)
    balance = fields.Monetary(
        currency_field='currency_id', compute='_compute_balance', store=True)
    record_type = fields.Selection(
        [('charge', 'Charge'), ('payment', 'Payment')],
        compute='_compute_record_type', store=True)

    # --- payment details ---------------------------------------------------
    payment_type = fields.Selection([
        ('cash', 'Cash'), ('bank', 'Bank Transfer'), ('mobile', 'Mobile Money'),
        ('cheque', 'Cheque'), ('card', 'Card')], tracking=True)
    sponsorship = fields.Selection(
        [('self', 'Self Sponsored'), ('sponsored', 'Sponsored')],
        default='self', required=True, tracking=True)
    sponsor_id = fields.Many2one('res.partner', string='Sponsor', tracking=True)
    reference = fields.Char(help="Bank / mobile money transaction reference", tracking=True)
    receipt_no = fields.Char(string='Receipt No.', readonly=True, copy=False)
    receipt_file = fields.Binary(string='Receipt', attachment=True)
    receipt_filename = fields.Char()

    # --- umti conventions --------------------------------------------------
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.user.company_id)

    # ----------------------------------------------------------------------
    @api.depends('student_id', 'academic_year_id', 'semester_id', 'receipt_no')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.receipt_no, rec.student_id.display_name,
                     rec.academic_year_id.name, rec.semester_id.name]
            rec.display_name = ' / '.join(p for p in parts if p) or _('New Fee Record')

    @api.depends('fee_structure_line_id.currency_id', 'company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = (rec.fee_structure_line_id.currency_id
                               or rec.company_id.currency_id
                               or self.env.company.currency_id)

    @api.depends('fee_structure_line_id.amount')
    def _compute_fee_amount(self):
        # Defaults to the fee structure amount but stays editable (bursaries etc.)
        for rec in self:
            rec.fee_amount = rec.fee_structure_line_id.amount or rec.fee_amount

    @api.depends('fee_amount', 'payment_amount')
    def _compute_balance(self):
        for rec in self:
            rec.balance = rec.fee_amount - rec.payment_amount

    @api.depends('fee_amount', 'payment_amount')
    def _compute_record_type(self):
        for rec in self:
            rec.record_type = 'payment' if rec.payment_amount else 'charge'

    @api.onchange('student_id')
    def _onchange_student_id(self):
        # Defaults only (no retroactive recompute): copy from the student file.
        student = self.student_id
        if student:
            self.course_id = student.course_id
            self.sponsorship = student.fee_status or 'self'
            self.sponsor_id = student.sponsor_id if student.fee_status == 'sponsored' else False

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        if self.semester_id and self.semester_id.academic_year_id != self.academic_year_id:
            self.semester_id = False
        self._onchange_clear_fee_line()

    @api.onchange('semester_id', 'course_id')
    def _onchange_clear_fee_line(self):
        line = self.fee_structure_line_id
        if line and (line.academic_year_id != self.academic_year_id
                     or line.course_id != self.course_id
                     or (line.semester_id and line.semester_id != self.semester_id)):
            self.fee_structure_line_id = False

    @api.constrains('academic_year_id', 'semester_id')
    def _check_semester_in_year(self):
        for rec in self:
            if rec.semester_id and rec.semester_id.academic_year_id != rec.academic_year_id:
                raise ValidationError(_("The semester does not belong to the selected academic year."))

    @api.constrains('fee_amount', 'payment_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.fee_amount < 0 or rec.payment_amount < 0:
                raise ValidationError(_("Amounts cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('payment_amount') and not vals.get('receipt_no'):
                vals['receipt_no'] = self.env['ir.sequence'].next_by_code('umti.fee.receipt')
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('payment_amount'):
            for rec in self.filtered(lambda r: not r.receipt_no):
                rec.receipt_no = self.env['ir.sequence'].next_by_code('umti.fee.receipt')
        return res
