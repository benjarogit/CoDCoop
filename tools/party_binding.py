"""Fail-closed boundary between authenticated launcher party and native game.

Compiled feature bits and UDP choice confirmation cannot substitute for native
owner/session/world/roster/resource acknowledgements. Bootstrap v2 currently
contains resource readiness only and cannot bind an individual kit.
"""

def require_native_party_binding(party, native_capability=None, native_ack=None):
    if not isinstance(party, dict) or party.get('runtime_ready') is not False:
        raise ValueError('Invalid authenticated launcher party projection')
    if not isinstance(native_capability, dict) or native_capability.get('party_binding') != 'uf-party-owner-plan-v1':
        raise ValueError('Native individual-equipment party binding is unavailable; lobby choices are not applied')
    # There is deliberately no boolean override. Native State19/resource-v2
    # lacks signed owner/roster/plan acknowledgement. A later native integration
    # must implement and test that identity tuple before enabling this path.
    raise ValueError('Native owner/session/world/roster/plan/resource acknowledgement is not implemented')
