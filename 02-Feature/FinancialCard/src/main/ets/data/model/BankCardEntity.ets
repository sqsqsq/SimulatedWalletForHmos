import { TransactionRecord } from './TransactionRecord';

export enum CardCategoryKind {
  BANK_CARD = 'bank_card',
  TRANSIT = 'transit',
  ACCESS = 'access'
}

export enum BankCardProductType {
  DEBIT = 'debit',
  CREDIT = 'credit'
}

export interface BankCardEntity {
  cardNumber: string;
  cardCategory: CardCategoryKind;
  bankName: string;
  productType: BankCardProductType;
  addedAt: number;
  huaweiPayEnabled: boolean;
  unionPayEnabled: boolean;
  transactions: TransactionRecord[];
}
