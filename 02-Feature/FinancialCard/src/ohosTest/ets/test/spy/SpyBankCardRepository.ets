import { BankCardRepository } from '../../../../main/ets/data/repository/BankCardRepository';
import { BankCardEntity } from '../../../../main/ets/data/model/BankCardEntity';

class InsertSlot {
  private fail: boolean = false;

  returns(): void {
    this.fail = false;
  }

  fails(): void {
    this.fail = true;
  }

  shouldFail(): boolean {
    return this.fail;
  }
}

export class SpyBankCardRepository extends BankCardRepository {
  readonly callLog: string[] = [];
  readonly whenInsertCard: InsertSlot = new InsertSlot();

  override async insertCard(entity: BankCardEntity): Promise<boolean> {
    this.callLog.push('insertCard');
    if (this.whenInsertCard.shouldFail()) {
      return false;
    }
    return super.insertCard(entity);
  }

  override async queryAllBankCards(): Promise<BankCardEntity[]> {
    this.callLog.push('queryAllBankCards');
    return super.queryAllBankCards();
  }
}
