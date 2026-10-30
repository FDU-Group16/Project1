// Runs the real Python input validator. No HTTP or database is involved.
// M2_CONTRACT_PYTHON can select an existing project Python environment.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import test from 'node:test';
import { prepareDraft } from '../draft.ts';

const root = fileURLToPath(new URL('../../../../../../', import.meta.url));
const python = process.env.M2_CONTRACT_PYTHON || join(root, '.venv', 'bin', 'python');
const validate = String.raw`
import json, sys
from pydantic import ValidationError
from services.m2.contracts import ApplicationCreate
results = []
for payload in json.load(sys.stdin):
    try:
        value = ApplicationCreate.model_validate(payload)
        results.append({"accepted": True, "purpose": value.purpose})
    except ValidationError as exc:
        results.append({"accepted": False, "fields": [e["loc"][0] for e in exc.errors()]})
print(json.dumps(results))
`;

test('browser draft purpose boundaries agree with the real ApplicationCreate validator', () => {
  const cases = [
    '', ' \t\n', '论'.repeat(500), '𠮷'.repeat(500), '😀'.repeat(500),
    '会😀'.repeat(250), 'e\u0301'.repeat(250), ` \t${'𠮷'.repeat(500)}\n `,
    '论'.repeat(501), '𠮷'.repeat(501), '会😀'.repeat(250) + '议',
    'e\u0301'.repeat(250) + 'e',
  ];
  const base = { roomId: 'opaque-room', startLocal: '2030-01-01T10:00',
    endLocal: '2030-01-01T11:00', purpose: '讨论', attendeeCount: '2' };
  const now = Date.parse('2026-01-01T00:00:00Z');
  const baseline = prepareDraft(base, now).draft;
  assert.ok(baseline);
  const frontend = cases.map(purpose => prepareDraft({ ...base, purpose }, now));
  // Accepted cases send actual frontend output. Rejected cases send the same
  // input with known-valid non-purpose fields to compare rejection boundaries.
  const payloads = cases.map((purpose, i) => frontend[i].draft ?? { ...baseline, purpose });
  const result = spawnSync(python, ['-c', validate], { cwd: root,
    input: JSON.stringify(payloads), encoding: 'utf8', timeout: 15_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const backend = JSON.parse(result.stdout);
  assert.equal(backend.length, cases.length);
  for (const [i, { draft, errors }] of frontend.entries()) {
    assert.equal(draft !== null, backend[i].accepted, `case ${i}`);
    if (draft) assert.equal(draft.purpose, backend[i].purpose, `case ${i}`);
    else {
      assert.deepEqual(Object.keys(errors), ['purpose']);
      assert.deepEqual(backend[i].fields, ['purpose']);
    }
  }
});
