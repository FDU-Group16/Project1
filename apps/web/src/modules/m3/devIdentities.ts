// TEMPORARY-DEPENDENCY TEMP-M3-D-01: synthetic identities, only rendered in server-confirmed development mode.
// Remove alongside the module selector after real shared authentication integration; never accept these in production.
export const devIdentities = [
  { token: 'demo-student', label: '报修人 A · 合成身份' },
  { token: 'demo-student-2', label: '报修人 B · 合成身份' },
  { token: 'demo-dispatcher', label: '物业调度 · 合成身份' },
  { token: 'demo-technician', label: '维修人员 A · 合成身份' },
  { token: 'demo-technician-2', label: '维修人员 B · 合成身份' },
];
