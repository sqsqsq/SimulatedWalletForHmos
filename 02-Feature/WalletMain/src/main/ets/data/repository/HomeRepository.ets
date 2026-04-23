import { PromoInfo } from '../model/PromoInfo';
import { ServiceEntry } from '../model/ServiceEntry';
import { HomeDataPort } from '../port/HomeDataPort';

export class HomeRepository implements HomeDataPort {
  async getServiceEntries(): Promise<ServiceEntry[]> {
    // 与 acceptance AC-5 data_constraints.items_include 对齐；文案在 string.json
    return [
      { id: 's1', name: $r('app.string.home_mock_service_s1_name'), icon: $r('sys.symbol.creditcard') },
      { id: 's2', name: $r('app.string.home_mock_service_s2_name'), icon: $r('sys.symbol.doc_plaintext') },
      { id: 's3', name: $r('app.string.home_mock_service_s3_name'), icon: $r('sys.symbol.gift') },
      { id: 's4', name: $r('app.string.home_mock_service_s4_name'), icon: $r('sys.symbol.square_grid_2x2') }
    ];
  }

  async getPromoList(): Promise<PromoInfo[]> {
    return [
      {
        id: 'p1',
        title: $r('app.string.home_mock_promo_p1_title'),
        description: $r('app.string.home_mock_promo_p1_desc'),
        image: $r('sys.symbol.camera')
      },
      {
        id: 'p2',
        title: $r('app.string.home_mock_promo_p2_title'),
        description: $r('app.string.home_mock_promo_p2_desc'),
        image: $r('sys.symbol.lock')
      }
    ];
  }
}
