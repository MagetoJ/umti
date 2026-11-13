from odoo import api, fields, models, _


class UmtiStudentServiceType(models.Model):
    _name = 'umti.student.service.type'
    _description = 'Student Service Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(default='fa-life-ring')
    confidential = fields.Boolean(
        help="Only members of the allowed groups see the related cases.")
    group_ids = fields.Many2many(
        'res.groups', 'umti_service_type_group_rel', 'type_id', 'group_id',
        string='Allowed Groups')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Service type code must be unique.'),
    ]


class UmtiStudentServiceCase(models.Model):
    _name = 'umti.student.service.case'
    _description = 'Student Service Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Subject', required=True, tracking=True)
    service_type_id = fields.Many2one(
        'umti.student.service.type', string='Service', required=True,
        tracking=True, ondelete='restrict',
        domain="[('active', '=', True)]")
    student_id = fields.Many2one(
        'school.student', string='Student', required=True,
        tracking=True, ondelete='cascade', index=True)
    course_id = fields.Many2one(
        'umti.course', related='student_id.course_id', store=True,
        readonly=True)
    student_state = fields.Selection(
        related='student_id.state', store=True, readonly=True)
    assigned_to = fields.Many2one(
        'res.users', string='Assigned To', tracking=True,
        default=lambda self: self.env.user)
    priority = fields.Selection([
        ('low', 'Low'), ('normal', 'Normal'),
        ('high', 'High'), ('urgent', 'Urgent'),
    ], default='normal', required=True, tracking=True)
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='new', required=True, tracking=True)
    opened_date = fields.Date(
        default=fields.Date.context_today, tracking=True)
    closed_date = fields.Date(readonly=True, tracking=True)
    description = fields.Text()
    resolution = fields.Text()
    start_date = fields.Date()
    end_date = fields.Date()
    location = fields.Char()
    external_party = fields.Char(
        help="Employer, sponsor, hospital, transport provider, etc.")
    reference = fields.Char()
    amount = fields.Monetary(
        currency_field='currency_id',
        help="Welfare, scholarship or other monetary value.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'umti_service_case_attachment_rel', 'case_id',
        'attachment_id', string='Attachments')
    confidential = fields.Boolean(
        related='service_type_id.confidential', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_hold(self):
        self.write({'state': 'on_hold'})

    def action_resolve(self):
        self.write({
            'state': 'resolved',
            'closed_date': fields.Date.context_today(self),
        })

    def action_close(self):
        self.write({
            'state': 'closed',
            'closed_date': fields.Date.context_today(self),
        })

    def action_cancel(self):
        self.write({
            'state': 'cancelled',
            'closed_date': fields.Date.context_today(self),
        })

    def action_reopen(self):
        self.write({'state': 'new', 'closed_date': False})
