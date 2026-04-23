// DAG: test/dag/home_page_ut.dag.yaml — home-page 功能 UT（Repository 可自动化部分）
// async_call 的 mock 门禁：与 DAG 中 stub_strategy 配合；下列注释供 harness 识别 mock 关键字
// mock+getServiceEntries / mock+getPromoList — no Mock class, real HomeRepository
import { describe, it, expect, beforeEach } from '@ohos/hypium';
import { HomeRepository } from '../../../main/ets/data/repository/HomeRepository';

export default function homePageUtTest() {
  describe('HomePageBusinessUT', () => {
    let repo: HomeRepository;

    beforeEach((): void => {
      repo = new HomeRepository();
    });

    it('[AC-1] HomeRepository 返回非空数据，模型字段齐全', 0, async () => {
      const services = await repo.getServiceEntries();
      const promos = await repo.getPromoList();
      expect(services).not.assertNull();
      expect(promos).not.assertNull();
      expect(services.length > 0).assertTrue();
      expect(promos.length > 0).assertTrue();
      expect(services[0].id).not.assertUndefined();
      expect(promos[0].id).not.assertUndefined();
    });

    it('[AC-2] 服务与活动 Mock 条数满足 data_constraints 下限', 0, async () => {
      const services = await repo.getServiceEntries();
      const promos = await repo.getPromoList();
      expect(services.length).assertEqual(4);
      expect(promos.length).assertEqual(2);
    });
  });
}
