"""Assessment type definitions shared by the exam models.

Any type can be created at any time. How much an assessment counts toward the
unit's final mark is its own ``weight`` (%): the weights of the assessments of
a unit in a semester should total 100.
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

#: Types that summarise into the CAT / Assignment / Exam columns of a result.
CORE_TYPES = ('cat', 'assignment', 'final')

#: Suggested weight (%) when a new assessment of this type is created.
#: It is only a starting point: the user can change it freely.
DEFAULT_CORE_WEIGHTS = {'cat': 20.0, 'assignment': 10.0, 'final': 70.0}
