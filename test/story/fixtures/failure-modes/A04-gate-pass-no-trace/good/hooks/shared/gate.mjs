import { writePostCheckEvidence } from './evidence.mjs';
export function gate(ctx, r) {
  writePostCheckEvidence(ctx, { checks: r?.checks ?? [], inputs: r?.inputs ?? [] });
  return (r?.problems ?? []).length ? { ok: false, severityOverride: 'BLOCKER' } : { ok: true };
}
