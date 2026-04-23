import { HomeDataPort } from '../../../../main/ets/data/port/HomeDataPort';
import { PromoInfo } from '../../../../main/ets/data/model/PromoInfo';
import { ServiceEntry } from '../../../../main/ets/data/model/ServiceEntry';

/**
 * HomeDataPort 测试替身：
 * - 通过 `whenXxx.returns(...)` / `whenXxx.throws(...)` 预设返回值；
 * - 通过 `callLog` 记录方法调用顺序供断言。
 *
 * 严禁引入任何 UI 符号（@Component / NavPathStack / showToast 等）。
 */
class StubBehavior<T> {
  private _value?: T;
  private _error?: Error;

  returns(value: T): void {
    this._value = value;
    this._error = undefined;
  }

  throws(error: Error): void {
    this._error = error;
    this._value = undefined;
  }

  async resolve(): Promise<T> {
    if (this._error) {
      throw this._error;
    }
    if (this._value === undefined) {
      throw new Error('SpyHomeDataPort: behavior not configured');
    }
    return this._value;
  }
}

export class SpyHomeDataPort implements HomeDataPort {
  readonly whenGetServiceEntries: StubBehavior<ServiceEntry[]> = new StubBehavior<ServiceEntry[]>();
  readonly whenGetPromoList: StubBehavior<PromoInfo[]> = new StubBehavior<PromoInfo[]>();
  readonly callLog: string[] = [];

  async getServiceEntries(): Promise<ServiceEntry[]> {
    this.callLog.push('getServiceEntries');
    return await this.whenGetServiceEntries.resolve();
  }

  async getPromoList(): Promise<PromoInfo[]> {
    this.callLog.push('getPromoList');
    return await this.whenGetPromoList.resolve();
  }
}
