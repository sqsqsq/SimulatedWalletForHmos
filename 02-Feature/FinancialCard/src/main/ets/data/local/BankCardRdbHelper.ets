import { relationalStore } from '@kit.ArkData';
import { BankCardConstants } from '../../shared/constant/BankCardConstants';

const CREATE_TABLE_SQL: string =
  `CREATE TABLE IF NOT EXISTS ${BankCardConstants.RDB_TABLE} (` +
  'card_number TEXT PRIMARY KEY NOT NULL, ' +
  'card_category TEXT NOT NULL, ' +
  'bank_name TEXT NOT NULL, ' +
  'product_type TEXT NOT NULL, ' +
  'added_at INTEGER NOT NULL, ' +
  'huawei_pay_enabled INTEGER NOT NULL, ' +
  'union_pay_enabled INTEGER NOT NULL, ' +
  'transactions TEXT NOT NULL)';

export class BankCardRdbHelper {
  private static store: relationalStore.RdbStore | null = null;

  static async getStore(context: Context): Promise<relationalStore.RdbStore> {
    if (BankCardRdbHelper.store !== null) {
      return BankCardRdbHelper.store;
    }
    const config: relationalStore.StoreConfig = {
      name: BankCardConstants.RDB_NAME,
      securityLevel: relationalStore.SecurityLevel.S1
    };
    BankCardRdbHelper.store = await relationalStore.getRdbStore(context, config);
    await BankCardRdbHelper.store.executeSql(CREATE_TABLE_SQL);
    return BankCardRdbHelper.store;
  }

  static resetForTest(): void {
    BankCardRdbHelper.store = null;
  }
}
