def migrate(cr, version):
    """Obsolete: assessment plans were removed in 18.0.1.3.0.

    Kept as a no-op so databases upgrading from before 18.0.1.1.0 do not try
    to use the removed ``umti.assessment.plan`` model. Weights are now set on
    each assessment and migrated in 18.0.1.3.0.
    """
    return
