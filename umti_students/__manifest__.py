{
    'name': 'UMTI Students',
    'version': '18.0.2.0.0',
    'summary': 'Admissions, student records, fees, exams, review popup and student portal',
    'category': 'Education',
    # Compare with your old manifests (git show HEAD:school_student/__manifest__.py)
    # and add any other module they depended on.
    'depends': ['base', 'umti_core', 'mail', 'portal', 'account', ],
    'data': [
        # 1. Groups and access rights
        'data/umti_students_group_category.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        # 2. Sequences
        'data/ir_sequence_data.xml',
        'data/umti_fee_receipt_sequence.xml',
        'views/umti_student_views.xml',
        'views/umti_student_semester_views.xml',
        'views/umti_library_books_views.xml',
        'views/umti_library_lending_views.xml',
        'views/umti_kits_views.xml',
        'views/umti_kits_issuances_views.xml',
        'views/umti_student_admission_views.xml',
        'views/umti_admission_intake_views.xml',
        'views/umti_admission_application_views.xml',
        'views/umti_exam_record_views.xml',
        'views/umti_fee_record_views.xml',
        'views/umti_student_portfolio_views.xml',
        'views/umti_admission_review_views.xml',
        'views/umti_admission_payment_wizard_views.xml',
        'views/umti_menu_item_views.xml',
        'views/umti_student_form_inherit.xml',
        'views/umti_dashboard_views.xml',
        'views/umti_core_menu_icon.xml',
        # 5. Portal page
        'views/umti_portal_templates.xml',
    ],


    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
