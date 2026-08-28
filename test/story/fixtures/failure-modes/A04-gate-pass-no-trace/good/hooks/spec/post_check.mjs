import { gate } from '../shared/gate.mjs';
export default async function specPostCheck(ctx) {
  return gate(ctx, { problems: [] });
}
