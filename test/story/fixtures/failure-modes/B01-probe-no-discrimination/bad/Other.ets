// 这里的注释提到了 Orphan，但没有真的调用它——探针不该被注释骗过。
export class Other {
  run(): string { return 'x'; }
}
