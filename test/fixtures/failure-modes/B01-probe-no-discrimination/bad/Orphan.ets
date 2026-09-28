// 反例：角色类零调用——只在自己的定义文件里出现。
export class Orphan {
  next(step: string): string { return step; }
}
