# -*- coding: utf-8 -*-
# Base models first. A model that _inherit-s another must be imported after it.
from . import umti_student
from . import umti_fee_record
from . import umti_student_guardian
from . import umti_student_document
from . import umti_admission_intake
from . import umti_admission_document
from . import umti_admission_requirement
from . import umti_admission_application
from . import umti_admission_payment_wizard
from . import umti_course_inherit
from . import umti_student_admission
# Portfolio and review additions
from . import umti_student_portfolio
from . import umti_exam_record
from . import umti_admission_review
from . import umti_library_books
from . import umti_library_lending
from . import umti_kits
from . import umti_kits_issuance
from . import umti_student_semester
# Area dashboards
from . import umti_dashboard_students
from . import umti_dashboard_library
from . import umti_dashboard_kits
