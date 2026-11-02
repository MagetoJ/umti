"""Assessment type definitions shared by the exam models.

Only the CORE types feed the final unit mark. The OPTIONAL types can be
switched on per department and semester (see ``umti.assessment.plan``) but are
recorded for information only.
"""

ASSESSMENT_TYPES = [
    ('midterm', 'Mid-Term'),
    ('final', 'Final Exam'),
    ('cat', 'CAT / Test'),
    ('quiz', 'Quiz'),
    ('assignment', 'Assignment'),
    ('practical', 'Practical Assessment'),
    ('project', 'Project'),
]

#: Types that are always enabled and compute to the final mark.
CORE_TYPES = ('cat', 'assignment', 'final')

#: Types the HOD may enable per semester; they never count to the final mark.
OPTIONAL_TYPES = ('midterm', 'quiz', 'practical', 'project')

#: Default split of the final mark between the three core components (sums to 100).
DEFAULT_CORE_WEIGHTS = {'cat': 20.0, 'assignment': 10.0, 'final': 70.0}
