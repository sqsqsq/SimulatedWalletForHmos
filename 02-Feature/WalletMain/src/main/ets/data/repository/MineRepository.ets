import { FinanceEntry } from '../model/FinanceEntry';
import { SettingEntry } from '../model/SettingEntry';

export class MineRepository {
  async getFinanceEntries(): Promise<FinanceEntry[]> {
    // 与 acceptance AC-8 data_constraints.exact_items 对齐
    return [
      { id: 'f1', name: '银行卡交易记录', icon: $r('sys.symbol.doc_text') },
      { id: 'f2', name: '交通卡退款记录', icon: $r('sys.symbol.map') }
    ];
  }

  async getSettingEntries(): Promise<SettingEntry[]> {
    // 与 acceptance AC-9 data_constraints.exact_items 对齐
    return [
      { id: 'st1', name: '设置', icon: $r('sys.symbol.gearshape') },
      { id: 'st2', name: '帮助与客服', icon: $r('sys.symbol.questionmark_circle') }
    ];
  }
}
