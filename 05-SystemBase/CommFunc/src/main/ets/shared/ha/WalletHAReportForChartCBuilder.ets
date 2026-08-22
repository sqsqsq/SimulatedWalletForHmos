import { hiAppEvent } from '@kit.PerformanceAnalysisKit';

import { Logger } from '../log/Logger';
import { WalletHAEventID } from './WalletHAEventID';
import { WalletHAReportBaseCBuilder } from './WalletHAReportBaseCBuilder';

const REPORT_DOMAIN: string = 'WalletHA';
const REPORT_TAG: string = 'WalletHAReport';

export class WalletHAReportForChartCBuilder extends WalletHAReportBaseCBuilder {
  private readonly eventID: WalletHAEventID;

  constructor(eventID: WalletHAEventID, funcID: string, subFuncID: string) {
    super();
    this.eventID = eventID;
    this.setFuncID(funcID);
    this.setSubFuncID(subFuncID);
  }

  report(): void {
    this.setReportParam('WalletEventID', `${this.funcIDValue}_${this.subFuncIDValue}`);
    try {
      const reportPromise: Promise<void> = hiAppEvent.write({
        domain: REPORT_DOMAIN,
        name: this.eventID,
        eventType: hiAppEvent.EventType.STATISTIC,
        params: this.getReportParams()
      });
      reportPromise.catch((error: Object): void => {
        this.logReportFailure(error);
      });
    } catch (error) {
      this.logReportFailure(error);
    }
  }

  private logReportFailure(error: Object): void {
    Logger.error(REPORT_TAG, 'wallet Chart report failed: %{public}s', String(error));
  }
}
