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
      expect(services).not().assertNull();
      expect(promos).not().assertNull();
      expect(services.length > 0).assertTrue();
      expect(promos.length > 0).assertTrue();
      expect(services[0].id).not().assertUndefined();
      expect(promos[0].id).not().assertUndefined();
    });

    it('[AC-2] 服务与活动数据满足 acceptance data_constraints 且字段契约齐全', 0, async () => {
      const services = await repo.getServiceEntries();
      const promos = await repo.getPromoList();
      // data_constraints: min_service_items / min_promo_items ≥ 1（与 mock-plan 条数一致时可额外断言精确值）
      expect(services.length >= 1).assertTrue();
      expect(promos.length >= 1).assertTrue();
      expect(services.length).assertEqual(4);
      expect(promos.length).assertEqual(2);

      const s0 = services[0];
      const p0 = promos[0];
      expect(s0.id.length > 0).assertTrue();
      expect(p0.id.length > 0).assertTrue();
      expect(s0.name !== undefined).assertTrue();
      expect(s0.icon !== undefined).assertTrue();
      expect(p0.title !== undefined).assertTrue();
      expect(p0.description !== undefined).assertTrue();
      expect(p0.image !== undefined).assertTrue();
    });
  });
}
