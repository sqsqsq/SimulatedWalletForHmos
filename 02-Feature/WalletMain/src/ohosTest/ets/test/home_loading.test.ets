// DAG: test/dag/home_loading.dag.yaml
// UseCase: 02-Feature/WalletMain/src/main/ets/domain/usecase/HomeLoadingUseCase.ets
// 严禁 import 任何 UI / Nav / Toast 符号；仅允许 hypium + 被测 UseCase + 端口 + Spy + 数据模型
import { describe, it, expect, beforeEach } from '@ohos/hypium';
import { HomeLoadingUseCase, HomePhase } from '../../../main/ets/domain/usecase/HomeLoadingUseCase';
import { PromoInfo } from '../../../main/ets/data/model/PromoInfo';
import { ServiceEntry } from '../../../main/ets/data/model/ServiceEntry';
import { SpyHomeDataPort } from './spy/SpyHomeDataPort';

// UT 不允许 import/调用任何 UI 符号（包括 `$r`）；`Resource` 字段用类型断言的空对象作为占位。
const FAKE_RES: Resource = {} as Resource;

function fakeServices(): ServiceEntry[] {
  return [
    { id: 's1', name: FAKE_RES, icon: FAKE_RES },
    { id: 's2', name: FAKE_RES, icon: FAKE_RES }
  ];
}

function fakePromos(): PromoInfo[] {
  return [
    {
      id: 'p1',
      title: FAKE_RES,
      description: FAKE_RES,
      image: FAKE_RES
    }
  ];
}

export default function homeLoadingUseCaseTest() {
  describe('HomeLoadingUseCase', () => {
    let repo: SpyHomeDataPort;
    let useCase: HomeLoadingUseCase;

    beforeEach((): void => {
      repo = new SpyHomeDataPort();
      useCase = new HomeLoadingUseCase(repo);
    });

    it('[BRANCH-happy_load][AC-1][AC-2] 服务与活动均有数据时，状态到 Success 且端口顺序正确', 0, async () => {
      repo.whenGetServiceEntries.returns(fakeServices());
      repo.whenGetPromoList.returns(fakePromos());

      expect(useCase.state.phase).assertEqual(HomePhase.Idle);

      await useCase.onAppear();

      expect(useCase.state.phase).assertEqual(HomePhase.Success);
      expect(useCase.state.services.length).assertEqual(2);
      expect(useCase.state.promos.length).assertEqual(1);
      expect(useCase.state.errorCode).assertNull();
      expect(repo.callLog.length).assertEqual(2);
      expect(JSON.stringify(repo.callLog))
        .assertEqual(JSON.stringify(['getServiceEntries', 'getPromoList']));
    });

    it('[BRANCH-empty_services][BD-2] 服务列表为空时，状态仍为 Success 但 services 长度为 0', 0, async () => {
      repo.whenGetServiceEntries.returns([]);
      repo.whenGetPromoList.returns(fakePromos());

      await useCase.onAppear();

      expect(useCase.state.phase).assertEqual(HomePhase.Success);
      expect(useCase.state.services.length).assertEqual(0);
      expect(useCase.state.promos.length).assertEqual(1);
      expect(useCase.state.errorCode).assertNull();
      expect(repo.callLog.length).assertEqual(2);
      expect(JSON.stringify(repo.callLog))
        .assertEqual(JSON.stringify(['getServiceEntries', 'getPromoList']));
    });

    it('[BRANCH-empty_promos][BD-2] 活动列表为空时，状态仍为 Success 但 promos 长度为 0', 0, async () => {
      repo.whenGetServiceEntries.returns(fakeServices());
      repo.whenGetPromoList.returns([]);

      await useCase.onAppear();

      expect(useCase.state.phase).assertEqual(HomePhase.Success);
      expect(useCase.state.services.length).assertEqual(2);
      expect(useCase.state.promos.length).assertEqual(0);
      expect(useCase.state.errorCode).assertNull();
      expect(repo.callLog.length).assertEqual(2);
      expect(JSON.stringify(repo.callLog))
        .assertEqual(JSON.stringify(['getServiceEntries', 'getPromoList']));
    });

    it('[BRANCH-all_empty][BD-2] 两侧数据都为空时，状态落到 Empty', 0, async () => {
      repo.whenGetServiceEntries.returns([]);
      repo.whenGetPromoList.returns([]);

      await useCase.onAppear();

      expect(useCase.state.phase).assertEqual(HomePhase.Empty);
      expect(useCase.state.services.length).assertEqual(0);
      expect(useCase.state.promos.length).assertEqual(0);
      expect(useCase.state.errorCode).assertNull();
      expect(repo.callLog.length).assertEqual(2);
      expect(JSON.stringify(repo.callLog))
        .assertEqual(JSON.stringify(['getServiceEntries', 'getPromoList']));
    });

    it('[BRANCH-repo_failure][AC-10][BD-1] getServiceEntries 抛异常时，状态 Failed 且数据回退为空', 0, async () => {
      repo.whenGetServiceEntries.throws(new Error('network'));
      repo.whenGetPromoList.returns(fakePromos());

      await useCase.onAppear();

      expect(useCase.state.phase).assertEqual(HomePhase.Failed);
      expect(useCase.state.errorCode).assertEqual('LOAD_ERR');
      expect(useCase.state.services.length).assertEqual(0);
      expect(useCase.state.promos.length).assertEqual(0);
      expect(repo.callLog.length).assertEqual(1);
      expect(JSON.stringify(repo.callLog))
        .assertEqual(JSON.stringify(['getServiceEntries']));
    });
  });
}
