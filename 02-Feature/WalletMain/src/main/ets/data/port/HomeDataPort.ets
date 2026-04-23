import { PromoInfo } from '../model/PromoInfo';
import { ServiceEntry } from '../model/ServiceEntry';

/**
 * 首页数据端口（hexagonal port），解耦 UseCase 与具体数据源实现。
 * HomeRepository 作为 local 适配器实现该接口；UT 注入 SpyHomeDataPort 即可。
 *
 * 放置于 data 层：按 module_inner_layers [shared, data, domain, presentation]，
 * domain 可向下 import data，data 内部可互相引用；反过来不允许。
 */
export interface HomeDataPort {
  getServiceEntries(): Promise<ServiceEntry[]>;

  getPromoList(): Promise<PromoInfo[]>;
}
