import assert from 'node:assert/strict';
import test from 'node:test';
import { prepareDraft } from '../draft.ts';

const now = Date.parse('2026-10-29T00:00:00Z');
const valid = {
  roomId: 'room-opaque-7',
  startLocal: '2026-10-30T10:00',
  endLocal: '2026-10-30T11:30',
  purpose: '  学术讨论  ',
  attendeeCount: '12',
};

test('valid preview preserves room ID, trims purpose and emits UTC timestamps', () => {
  const { draft, errors } = prepareDraft(valid, now);
  assert.deepEqual(errors, {});
  assert.equal(draft?.room_id, valid.roomId);
  assert.equal(draft?.purpose, '学术讨论');
  assert.equal(draft?.attendee_count, 12);
  assert.match(draft?.start_at ?? '', /Z$/);
  assert.match(draft?.end_at ?? '', /Z$/);
  assert.equal(Date.parse(draft.end_at) - Date.parse(draft.start_at), 90 * 60_000);
  assert.deepEqual(Object.keys(draft).sort(), ['attendee_count', 'end_at', 'purpose', 'room_id', 'start_at']);
});

test('blank room and purpose never produce a preview', () => {
  const result = prepareDraft({ ...valid, roomId: ' ', purpose: '\t ' }, now);
  assert.equal(result.draft, null);
  assert.ok(result.errors.roomId);
  assert.ok(result.errors.purpose);
});

test('only positive safe integers are accepted as attendee counts', () => {
  for (const attendeeCount of ['0', '-1', '1.5', '01', '9007199254740992']) {
    const result = prepareDraft({ ...valid, attendeeCount }, now);
    assert.equal(result.draft, null, attendeeCount);
    assert.ok(result.errors.attendeeCount, attendeeCount);
  }
});

test('past, invalid and reversed intervals are rejected', () => {
  assert.ok(prepareDraft({ ...valid, startLocal: '2026-10-28T10:00' }, now).errors.startLocal);
  assert.ok(prepareDraft({ ...valid, startLocal: '2026-02-30T10:00' }, now).errors.startLocal);
  assert.ok(prepareDraft({ ...valid, endLocal: '2026-10-30T09:00' }, now).errors.endLocal);
  assert.ok(prepareDraft({ ...valid, endLocal: valid.startLocal }, now).errors.endLocal);
});

test('purpose is limited to the proposed input contract length', () => {
  assert.ok(prepareDraft({ ...valid, purpose: 'x'.repeat(501) }, now).errors.purpose);
});
