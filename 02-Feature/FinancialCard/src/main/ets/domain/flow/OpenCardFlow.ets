import { BankCatalogItem, SelectableBankCard } from '../../data/model/BankMockCatalog';
import { BankCardEntity, BankCardProductType, CardCategoryKind } from '../../data/model/BankCardEntity';
import { TransactionRecord } from '../../data/model/TransactionRecord';
import { BankCardRepository } from '../../data/repository/BankCardRepository';

export type OpenCardPhase =
  'Idle' | 'CardTypeSelected' | 'CardPicked' | 'SmsWaiting' | 'Persisting' | 'Success' | 'Failed';

export interface OpenCardSession {
  bank: BankCatalogItem;
  productType: BankCardProductType;
  selectedCard: SelectableBankCard;
  smsCode: string;
  resultSuccess: boolean;
  resultCardNumber: string;
}

@Observed
export class OpenCardFlowState {
  phase: OpenCardPhase = 'Idle';
  bank: BankCatalogItem | null = null;
  productType: BankCardProductType = BankCardProductType.DEBIT;
  selectedCard: SelectableBankCard | null = null;
  smsCode: string = '';
  resultSuccess: boolean = false;
  resultCardNumber: string = '';
  errorCode: string | null = null;
}

export class OpenCardFlow {
  private static instance: OpenCardFlow | null = null;
  readonly state: OpenCardFlowState = new OpenCardFlowState();
  private readonly repository: BankCardRepository = BankCardRepository.getInstance();

  static getInstance(): OpenCardFlow {
    if (OpenCardFlow.instance === null) {
      OpenCardFlow.instance = new OpenCardFlow();
    }
    return OpenCardFlow.instance;
  }

  reset(): void {
    this.state.phase = 'Idle';
    this.state.bank = null;
    this.state.productType = BankCardProductType.DEBIT;
    this.state.selectedCard = null;
    this.state.smsCode = '';
    this.state.resultSuccess = false;
    this.state.resultCardNumber = '';
    this.state.errorCode = null;
  }

  openCardTypeSheet(bank: BankCatalogItem): void {
    this.state.bank = bank;
    this.state.phase = 'CardTypeSelected';
  }

  navigateAllBanks(): void {
    this.state.phase = 'Idle';
  }

  confirmCardType(productType: BankCardProductType): void {
    this.state.productType = productType;
    this.state.phase = 'CardPicked';
  }

  pickCard(card: SelectableBankCard): void {
    this.state.selectedCard = card;
    this.state.phase = 'CardPicked';
  }

  openSmsSheet(): void {
    this.state.phase = 'SmsWaiting';
  }

  async submitSmsAndBind(code: string): Promise<OpenCardSession> {
    this.state.smsCode = code;
    this.state.phase = 'Persisting';
    const session: OpenCardSession = this.buildSession();
    const completed: OpenCardSession = await this.completeBinding(session);
    this.state.resultSuccess = completed.resultSuccess;
    this.state.resultCardNumber = completed.resultCardNumber;
    this.state.phase = completed.resultSuccess ? 'Success' : 'Failed';
    return completed;
  }

  async completeBinding(session: OpenCardSession): Promise<OpenCardSession> {
    const entity: BankCardEntity = {
      cardNumber: session.selectedCard.fullNumber,
      cardCategory: CardCategoryKind.BANK_CARD,
      bankName: session.bank.name,
      productType: session.productType,
      addedAt: Date.now(),
      huaweiPayEnabled: true,
      unionPayEnabled: true,
      transactions: OpenCardFlow.buildMockTransactions()
    };
    const ok: boolean = await this.repository.insertCard(entity);
    return {
      bank: session.bank,
      productType: session.productType,
      selectedCard: session.selectedCard,
      smsCode: session.smsCode,
      resultSuccess: ok,
      resultCardNumber: session.selectedCard.fullNumber
    };
  }

  popOpenCardStackAndNavigate(_result: OpenCardSession): void {
    this.reset();
  }

  finishAndPopStack(): OpenCardSession {
    const session: OpenCardSession = this.buildSession();
    this.popOpenCardStackAndNavigate(session);
    return session;
  }

  buildSession(): OpenCardSession {
    return {
      bank: this.state.bank as BankCatalogItem,
      productType: this.state.productType,
      selectedCard: this.state.selectedCard as SelectableBankCard,
      smsCode: this.state.smsCode,
      resultSuccess: this.state.resultSuccess,
      resultCardNumber: this.state.resultCardNumber
    };
  }

  private static buildMockTransactions(): TransactionRecord[] {
    return [
      {
        id: 'tx1',
        merchantName: '商户消费',
        amount: -128.5,
        channel: '银联',
        occurredAt: Date.now() - 86400000
      }
    ];
  }
}
