"""TEMPORARY-DEPENDENCY M1-D-IDENTITY / M1-D-DELIVERY.

M1 为并行开发维护的临时替身，仅显式 dev/test 启用。
D-01 归 M2；D-03/D-04 归 M3。对应组可与 M1 在集成任务中修改/替换，
真实接口联调通过后按 README.md 清理；保留 M1 业务、真实 HTTP 客户端及错误处理。
"""
import os
from services.platform import Problem


# TEMPORARY-DEPENDENCY M1-D-IDENTITY：合成身份可由 M1/M2 协调修改或替换；不实现 M2 的账号服务。
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


# TEMPORARY-DEPENDENCY M1-D-DELIVERY：模拟接收/失败可由 M1/M3 协调修改或替换；不代表真实投递。
def development_deliver(kind, payload):
    # Failure injection exercises retry paths without implementing the provider.
    if os.getenv('M1_DEV_DELIVERY_FAIL') == '1':
        raise Problem(503, 'SIMULATED_DELIVERY_FAILURE', 'Development delivery failure enabled.')
