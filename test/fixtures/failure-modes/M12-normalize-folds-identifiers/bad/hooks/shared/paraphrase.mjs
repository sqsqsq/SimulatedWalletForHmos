export function normalize(s) {
  return s.replace(/\s+/g, '').replace(/[^\w]/g, '');
}
