import { CardCategory } from '../model/CardCategory';

export class CardRepository {
  async getCardCategories(): Promise<CardCategory[]> {
    // 与 acceptance AC-15 data_constraints.items 描述对齐
    return [
      {
        id: 'c1',
        name: '银行卡',
        description: '双击电源键便捷支付',
        icon: $r('sys.symbol.creditcard')
      },
      {
        id: 'c2',
        name: '交通卡',
        description: '一张卡可刷全国',
        icon: $r('sys.symbol.map')
      },
      {
        id: 'c3',
        name: '门禁卡',
        description: '手机就是门禁卡',
        icon: $r('sys.symbol.lock')
      },
      {
        id: 'c4',
        name: '车钥匙',
        description: '手机秒变车钥匙',
        icon: $r('sys.symbol.car')
      },
      {
        id: 'c5',
        name: '证件',
        description: '随时随地查看证件',
        icon: $r('sys.symbol.person')
      }
    ];
  }

  async getNonLocalCardCount(): Promise<number> {
    return 3;
  }
}
