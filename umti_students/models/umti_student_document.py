from odoo import api, fields, models


class SchoolStudentDocument(models.Model):
    """A scanned admission document kept on the student file.

    Documents that come from an admission application are linked to it: the
    file is read from the application line for the same requirement and is not
    copied onto the student.
    """
    _name = 'school.student.document'
    _description = 'Student Admission Document'

    student_id = fields.Many2one(
        'school.student', required=True, ondelete='cascade', index=True)
    application_id = fields.Many2one(
        'school.admission.application', string='Source Application',
        ondelete='cascade', index=True,
        help='When set, the file is read from this application instead of '
             'being stored on the document.')
    requirement_id = fields.Many2one(
        'umti.course.required.documents', string='Document', required=True,
        ondelete='restrict', index=True)
    document_name = fields.Char(related='requirement_id.name', store=True)
    number = fields.Char(string='Document No')
    attachment = fields.Binary(attachment=True)
    filename = fields.Char()
    application_line_id = fields.Many2one(
        'school.admission.document', string='Application File',
        compute='_compute_source_file')
    source_attachment = fields.Binary(
        string='Application File', compute='_compute_source_file')
    source_filename = fields.Char(compute='_compute_source_file')
    note = fields.Char()

    @api.depends(
        'application_id',
        'requirement_id',
        'application_id.document_ids.requirement_id',
        'application_id.document_ids.attachment',
    )
    def _compute_source_file(self):
        for rec in self:
            line = rec.application_id.document_ids.filtered(
                lambda doc: doc.requirement_id == rec.requirement_id)[:1]
            rec.application_line_id = line
            rec.source_attachment = line.attachment
            rec.source_filename = line.filename
