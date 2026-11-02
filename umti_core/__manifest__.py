# -*- coding: utf-8 -*-
{
    "name": "UMTI Core",
    "version": "18.0.1.2.0",
    "category": "Tools",
    "summary": "UMTI Core",
    "description": "This module provides the course as the core foundation of UMTI module as a whole.",
    "author": 'IBOS',
    "maintainer": "James Oginga",
    "website": 'https://www.ibos.co.ke',
    "depends": ["base","mail","account"],
    "data": [
        "data/module_presets.xml",
        "data/umti_group_category.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/umti_course_views.xml",
        "views/umti_department_views.xml",
        "views/umti_course_level_views.xml",
        "views/umti_course_units_views.xml",
        "views/umti_fee_structure_views.xml",
        "views/umti_academic_year_views.xml",
        "views/umti_academic_term_views.xml",
        "views/res_config_settings.xml",
        "views/umti_menu_item_views.xml",
        "views/umti_dashboard_views.xml",
        
    ],
    "assets": {
        "web.assets_backend": [
            "umti_core/static/src/dashboard/**/*.js",
            "umti_core/static/src/dashboard/**/*.xml",
            "umti_core/static/src/dashboard/**/*.scss",
        ],
    },
    "license": "OPL-1",
    "installable": True,
    "auto_install": False,
    "application": True
}