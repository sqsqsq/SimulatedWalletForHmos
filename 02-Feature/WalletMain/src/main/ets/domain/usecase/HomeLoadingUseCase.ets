import { HomeDataPort } from '../../data/port/HomeDataPort';
import { PromoInfo } from '../../data/model/PromoInfo';
import { ServiceEntry } from '../../data/model/ServiceEntry';

/**
 * 首页加载流程状态枚举。UI 层根据 phase 翻译成渲染/Toast 副作用。
 */
export enum HomePhase {
  Idle = 'Idle',
  Loading = 'Loading',
  Success = 'Success',
  Empty = 'Empty',
  Failed = 'Failed'
}

/**
 * UseCase 状态模型。保持纯数据，不含 UI 引用。
 * 使用 @Observed 使得 UI 层 @ObjectLink/@Watch 可以感知变化。
 */
@Observed
export class HomeLoadingState {
  phase: HomePhase = HomePhase.Idle;
  errorCode: string | null = null;
  services: ServiceEntry[] = [];
  promos: PromoInfo[] = [];
}

/**
 * HomeLoadingUseCase — 首页数据加载业务逻辑。
 *
 * 约束（遵循 framework/specs/phase-rules/coding-rules.yaml 的 UseCase 纯度规则）：
 * - 构造器注入所有外部依赖（ports），不得硬依赖具体 Repository 实现；
 * - 严禁 import 任何 UI 装饰器 / 导航栈 / Toast / ArkUI 相关符号；
 * - 只发布 state，不直接触发导航或界面反馈，这些由 UI 层订阅 state 翻译。
 *
 * 对应 use-cases.yaml > home_loading，分支覆盖见 DAG / UT。
 */
export class HomeLoadingUseCase {
  readonly state: HomeLoadingState = new HomeLoadingState();

  constructor(private readonly repo: HomeDataPort) {
  }

  async onAppear(): Promise<void> {
    this.state.phase = HomePhase.Loading;
    this.state.errorCode = null;
    try {
      const services = await this.repo.getServiceEntries();
      const promos = await this.repo.getPromoList();
      this.state.services = services;
      this.state.promos = promos;
      if (services.length === 0 && promos.length === 0) {
        this.state.phase = HomePhase.Empty;
      } else {
        this.state.phase = HomePhase.Success;
      }
    } catch (_e) {
      this.state.services = [];
      this.state.promos = [];
      this.state.errorCode = 'LOAD_ERR';
      this.state.phase = HomePhase.Failed;
    }
  }
}
