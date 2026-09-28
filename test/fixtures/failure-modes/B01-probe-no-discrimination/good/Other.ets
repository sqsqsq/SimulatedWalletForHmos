import { Orphan } from './Orphan';
export class Other {
  run(): string { return new Orphan().next('a'); }
}
