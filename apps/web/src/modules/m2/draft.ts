// A local preview of the proposed ApplicationCreate input. It never submits or stores data.
export interface DraftInput {
  roomId: string;
  startLocal: string;
  endLocal: string;
  purpose: string;
  attendeeCount: string;
}

export interface ApplicationDraft {
  room_id: string;
  start_at: string;
  end_at: string;
  purpose: string;
  attendee_count: number;
}

export type DraftErrors = Partial<Record<keyof DraftInput, string>>;

function localDateTime(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [, year, month, day, hour, minute] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute));
  if (date.getFullYear() !== Number(year) || date.getMonth() + 1 !== Number(month) ||
      date.getDate() !== Number(day) || date.getHours() !== Number(hour) ||
      date.getMinutes() !== Number(minute)) return null;
  return date;
}

export function prepareDraft(input: DraftInput, nowMs = Date.now()): { draft: ApplicationDraft | null; errors: DraftErrors } {
  const errors: DraftErrors = {};
  // D owns the identifier. Preserve its exact value; only reject blank input.
  if (!input.roomId.trim()) errors.roomId = '请输入房间 ID。';
  const purpose = input.purpose.trim();
  if (!purpose) errors.purpose = '请填写用途。';
  // Match ApplicationCreate / PostgreSQL char_length: Unicode code points,
  // not UTF-16 code units (which count supplementary characters twice).
  else if (Array.from(purpose).length > 500) errors.purpose = '用途不能超过 500 个字符。';
  if (!/^[1-9]\d*$/.test(input.attendeeCount)) errors.attendeeCount = '人数须为正整数。';
  const attendeeCount = Number(input.attendeeCount);
  if (!errors.attendeeCount && !Number.isSafeInteger(attendeeCount)) errors.attendeeCount = '人数超出可处理范围。';
  const start = localDateTime(input.startLocal);
  const end = localDateTime(input.endLocal);
  if (!start) errors.startLocal = '请选择有效的开始时间。';
  else if (start.getTime() <= nowMs) errors.startLocal = '开始时间须晚于当前时间。';
  if (!end) errors.endLocal = '请选择有效的结束时间。';
  else if (start && end.getTime() <= start.getTime()) errors.endLocal = '结束时间须晚于开始时间。';
  if (Object.keys(errors).length || !start || !end) return { draft: null, errors };
  return {
    draft: {
      room_id: input.roomId,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      purpose,
      attendee_count: attendeeCount,
    },
    errors,
  };
}
