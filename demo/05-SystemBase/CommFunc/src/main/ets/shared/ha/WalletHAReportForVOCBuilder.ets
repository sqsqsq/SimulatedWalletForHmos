import { hiAppEvent } from '@kit.PerformanceAnalysisKit';

import { Logger } from '../log/Logger';
import { WalletHAEventID } from './WalletHAEventID';
import { WalletHAReportBaseCBuilder } from './WalletHAReportBaseCBuilder';

const REPORT_DOMAIN: string = 'WalletHA';
const REPORT_TAG: string = 'WalletHAReport';

export class WalletHAReportForVOCBuilder extends WalletHAReportBaseCBuilder {
  constructor(walletEventID: string, walletEventDesc: string) {
    super();
    this.setReportParam('WalletEventID', walletEventID);
    this.setWalletEventDesc(walletEventDesc);
    this.setFuncID('VOC');
  }

  report(): void {
    try {
      const reportPromise: Promise<void> = hiAppEvent.write({
        domain: REPORT_DOMAIN,
        name: WalletHAEventID.Wallet_COMMON,
        eventType: hiAppEvent.EventType.BEHAVIOR,
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
    Logger.error(REPORT_TAG, 'wallet VOC report failed: %{public}s', String(error));
  }
}
