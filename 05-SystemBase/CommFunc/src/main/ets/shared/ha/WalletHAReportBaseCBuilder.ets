import { WalletFuncResult } from './WalletFuncResult';

export type WalletHAReportParam = string | number | boolean;
export type WalletHAReportParams = Record<string, WalletHAReportParam>;

export abstract class WalletHAReportBaseCBuilder {
  protected readonly params: WalletHAReportParams = {};
  protected funcIDValue: string = '';
  protected subFuncIDValue: string = '';

  abstract report(): void;

  setFuncID(funcID: string): WalletHAReportBaseCBuilder {
    this.funcIDValue = funcID;
    return this.setReportParam('FuncID', funcID);
  }

  setSubFuncID(subFuncID: string): WalletHAReportBaseCBuilder {
    this.subFuncIDValue = subFuncID;
    return this.setReportParam('SubFuncID', subFuncID);
  }

  setWalletFuncResult(result: WalletFuncResult): WalletHAReportBaseCBuilder {
    return this.setReportParam('WalletFuncResult', result);
  }

  setChannel(channel: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('Channel', channel);
  }

  setWalletEventDesc(walletEventDesc: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('WalletEventDesc', walletEventDesc);
  }

  setWalletEventInCode(walletEventInCode: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('WalletEventInCode', walletEventInCode);
  }

  setWalletEventExtCode(walletEventExtCode: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('WalletEventExtCode', walletEventExtCode);
  }

  setIssueID(issueID: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('IssueID', issueID);
  }

  setIssueName(issueName: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('IssueName', issueName);
  }

  setDuration(duration: number): WalletHAReportBaseCBuilder {
    return this.setReportParam('Duration', duration);
  }

  setSource(source: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('Source', source);
  }

  setOperationType(operationType: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('OperationType', operationType);
  }

  setSrcPassType(srcPassType: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('SrcPassType', srcPassType);
  }

  setOrderNumber(orderNumber: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('OrderNumber', orderNumber);
  }

  setTransactionId(transactionId: string): WalletHAReportBaseCBuilder {
    return this.setReportParam('TransactionId', transactionId);
  }

  setHappenedTime(happenedTime: string | number): WalletHAReportBaseCBuilder {
    return this.setReportParam('HappenedTime', happenedTime);
  }

  protected setReportParam(name: string, value: WalletHAReportParam): WalletHAReportBaseCBuilder {
    this.params[name] = value;
    return this;
  }

  protected getReportParams(): WalletHAReportParams {
    const reportParams: WalletHAReportParams = {};
    const names: string[] = Object.keys(this.params);
    for (const name of names) {
      reportParams[name] = this.params[name];
    }
    return reportParams;
  }
}
