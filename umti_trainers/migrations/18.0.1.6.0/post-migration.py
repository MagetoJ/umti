from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Point the (noupdate) trainer record rule at the enrollment trainer.

    Trainer assignment itself moved to umti.unit.trainer in 18.0.1.7.0.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    rule = env.ref(
        'umti_trainers.rule_enrollment_trainer', False)
    if rule:
        rule.write({
            'domain_force': "[('trainer_id.user_id', '=', user.id)]",
        })
    env.flush_all()
