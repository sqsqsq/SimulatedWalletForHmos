import { relationalStore } from '@kit.ArkData';
import { BankCardConstants } from '../../shared/constant/BankCardConstants';
import { BankCardEntity, CardCategoryKind, BankCardProductType } from '../model/BankCardEntity';
import { TransactionRecord } from '../model/TransactionRecord';
import { BankCardRdbHelper } from '../local/BankCardRdbHelper';

export class BankCardRepository {
  private static instance: BankCardRepository | null = null;
  private context: Context | null = null;
  private forceInsertFail: boolean = false;

  static getInstance(): BankCardRepository {
    if (BankCardRepository.instance === null) {
      BankCardRepository.instance = new BankCardRepository();
    }
    return BankCardRepository.instance;
  }

  async init(context: Context): Promise<void> {
    this.context = context;
    await BankCardRdbHelper.getStore(context);
  }

  setForceInsertFail(enabled: boolean): void {
    this.forceInsertFail = enabled;
  }

  async insertCard(entity: BankCardEntity): Promise<boolean> {
    if (this.forceInsertFail) {
      return false;
    }
    if (this.context === null) {
      return false;
    }
    const store: relationalStore.RdbStore = await BankCardRdbHelper.getStore(this.context);
    const values: relationalStore.ValuesBucket = {
      card_number: entity.cardNumber,
      card_category: entity.cardCategory,
      bank_name: entity.bankName,
      product_type: entity.productType,
      added_at: entity.addedAt,
      huawei_pay_enabled: entity.huaweiPayEnabled ? 1 : 0,
      union_pay_enabled: entity.unionPayEnabled ? 1 : 0,
      transactions: JSON.stringify(entity.transactions)
    };
    const rowId: number = await store.insert(BankCardConstants.RDB_TABLE, values);
    return rowId >= 0;
  }

  async queryAllBankCards(): Promise<BankCardEntity[]> {
    if (this.context === null) {
      return [];
    }
    const store: relationalStore.RdbStore = await BankCardRdbHelper.getStore(this.context);
    const predicates: relationalStore.RdbPredicates = new relationalStore.RdbPredicates(BankCardConstants.RDB_TABLE);
    predicates.orderByDesc('added_at');
    const resultSet: relationalStore.ResultSet = await store.query(predicates);
    const cards: BankCardEntity[] = [];
    while (resultSet.goToNextRow()) {
      cards.push(BankCardRepository.rowToEntity(resultSet));
    }
    resultSet.close();
    return cards;
  }

  async queryByCardNumber(cardNumber: string): Promise<BankCardEntity | null> {
    if (this.context === null) {
      return null;
    }
    const store: relationalStore.RdbStore = await BankCardRdbHelper.getStore(this.context);
    const predicates: relationalStore.RdbPredicates = new relationalStore.RdbPredicates(BankCardConstants.RDB_TABLE);
    predicates.equalTo('card_number', cardNumber);
    const resultSet: relationalStore.ResultSet = await store.query(predicates);
    let entity: BankCardEntity | null = null;
    if (resultSet.goToFirstRow()) {
      entity = BankCardRepository.rowToEntity(resultSet);
    }
    resultSet.close();
    return entity;
  }

  async countBankCards(): Promise<number> {
    const cards: BankCardEntity[] = await this.queryAllBankCards();
    return cards.length;
  }

  async deleteAllBankCards(): Promise<void> {
    if (this.context === null) {
      return;
    }
    const store: relationalStore.RdbStore = await BankCardRdbHelper.getStore(this.context);
    const predicates: relationalStore.RdbPredicates = new relationalStore.RdbPredicates(BankCardConstants.RDB_TABLE);
    await store.delete(predicates);
  }

  private static rowToEntity(resultSet: relationalStore.ResultSet): BankCardEntity {
    const txRaw: string = resultSet.getString(resultSet.getColumnIndex('transactions'));
    let transactions: TransactionRecord[] = [];
    try {
      transactions = JSON.parse(txRaw) as TransactionRecord[];
    } catch (_e) {
      transactions = [];
    }
    return {
      cardNumber: resultSet.getString(resultSet.getColumnIndex('card_number')),
      cardCategory: resultSet.getString(resultSet.getColumnIndex('card_category')) as CardCategoryKind,
      bankName: resultSet.getString(resultSet.getColumnIndex('bank_name')),
      productType: resultSet.getString(resultSet.getColumnIndex('product_type')) as BankCardProductType,
      addedAt: resultSet.getLong(resultSet.getColumnIndex('added_at')),
      huaweiPayEnabled: resultSet.getLong(resultSet.getColumnIndex('huawei_pay_enabled')) === 1,
      unionPayEnabled: resultSet.getLong(resultSet.getColumnIndex('union_pay_enabled')) === 1,
      transactions
    };
  }
}
