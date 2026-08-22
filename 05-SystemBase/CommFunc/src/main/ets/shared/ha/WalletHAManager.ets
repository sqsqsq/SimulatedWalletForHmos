import { Logger } from '../log/Logger';
import { WalletHAEventID } from './WalletHAEventID';
import { WalletHAReportForChartCBuilder } from './WalletHAReportForChartCBuilder';
import { WalletHAReportForVOCBuilder } from './WalletHAReportForVOCBuilder';

export class WalletHAManager {
  static vocBuilder(walletEventID: string, walletEventDesc: string): WalletHAReportForVOCBuilder {
    return new WalletHAReportForVOCBuilder(walletEventID, walletEventDesc);
  }

  static chartBuilder(
    eventID: WalletHAEventID,
    funcID: string,
    subFuncID: string
  ): WalletHAReportForChartCBuilder {
    return new WalletHAReportForChartCBuilder(eventID, funcID, subFuncID);
  }

  static logAndReport(walletEventID: string, walletEventDesc: string): void {
    Logger.info(walletEventID, walletEventDesc);
    WalletHAManager.vocBuilder(walletEventID, walletEventDesc).report();
  }

  static logErrorAndReport(walletEventID: string, walletEventDesc: string): void {
    Logger.error(walletEventID, walletEventDesc);
    WalletHAManager.vocBuilder(walletEventID, walletEventDesc).report();
  }

  static logDebugAndReport(walletEventID: string, walletEventDesc: string): void {
    Logger.debug(walletEventID, walletEventDesc);
    WalletHAManager.vocBuilder(walletEventID, walletEventDesc).report();
  }
}
