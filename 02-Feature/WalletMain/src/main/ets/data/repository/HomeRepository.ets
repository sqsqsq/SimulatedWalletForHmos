import { PromoInfo } from '../model/PromoInfo';
import { ServiceEntry } from '../model/ServiceEntry';

export class HomeRepository {
  async getServiceEntries(): Promise<ServiceEntry[]> {
    // 与 acceptance AC-5 data_constraints.items_include 对齐
    return [
      { id: 's1', name: 'Huawei Card', icon: $r('sys.symbol.creditcard') },
      { id: 's2', name: '信用卡还款', icon: $r('sys.symbol.doc_plaintext') },
      { id: 's3', name: '优惠加油', icon: $r('sys.symbol.gift') },
      { id: 's4', name: '更多', icon: $r('sys.symbol.square_grid_2x2') }
    ];
  }

  async getPromoList(): Promise<PromoInfo[]> {
    return [
      {
        id: 'p1',
        title: '春日出行',
        description: '交通卡充值满减',
        image: $r('sys.symbol.camera')
      },
      {
        id: 'p2',
        title: '安全用卡',
        description: '守护您的资金安全',
        image: $r('sys.symbol.lock')
      }
    ];
  }
}
