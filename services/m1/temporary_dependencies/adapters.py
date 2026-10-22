"""TEMPORARY-DEPENDENCY M1-D-IDENTITY / M1-D-DELIVERY: explicit dev/test only."""
import os
from services.platform import Problem


def development_identity(token):
    identities = {
        'dev-student-cs': {'departmentId': 'cs', 'permissions': ['seat:reserve']},
        'dev-student-ee': {'departmentId': 'ee', 'permissions': ['seat:reserve']},
        'dev-room-admin': {'departmentId': None, 'permissions': ['room:manage']},
        'dev-operator': {'departmentId': None, 'permissions': ['operations:read']},
    }
    if token not in identities:
        raise Problem(401, 'UNAUTHORIZED', 'Unknown development identity.')
    return {'id': token, **identities[token], 'dependencyMode': 'development-substitutes'}


def development_deliver(kind, payload):
    # Failure injection exercises retry paths without implementing the provider.
    if os.getenv('M1_DEV_DELIVERY_FAIL') == '1':
        raise Problem(503, 'SIMULATED_DELIVERY_FAILURE', 'Development delivery failure enabled.')
