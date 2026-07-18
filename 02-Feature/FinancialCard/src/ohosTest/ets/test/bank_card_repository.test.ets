import { describe, it, expect, beforeAll, beforeEach } from '@ohos/hypium';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import { BankCardRepository } from '../../../main/ets/data/repository/BankCardRepository';
import {
  BankCardEntity,
  BankCardProductType,
  CardCategoryKind
} from '../../../main/ets/data/model/BankCardEntity';
import { TransactionRecord } from '../../../main/ets/data/model/TransactionRecord';
import { SpyBankCardRepository } from './spy/SpyBankCardRepository';

export default function bankCardRepositoryTest(): void {
  describe('BankCardRepository', () => {
    let repo: BankCardRepository;
    let spyRepo: SpyBankCardRepository;
    let sampleEntity: BankCardEntity;

    beforeAll(async () => {
      repo = BankCardRepository.getInstance();
      const context = abilityDelegatorRegistry.getAbilityDelegator().getAppContext();
      await repo.init(context);
    });

    beforeEach(async (): Promise<void> => {
      repo = BankCardRepository.getInstance();
      spyRepo = new SpyBankCardRepository();
      spyRepo.whenInsertCard.returns();
      repo.setForceInsertFail(false);
      await repo.deleteAllBankCards();
      const tx: TransactionRecord = {
        id: 'tx1',
        merchantName: '商户消费',
        amount: -88.0,
        channel: '银联',
        occurredAt: Date.now()
      };
      sampleEntity = {
        cardNumber: '6222000000000101',
        cardCategory: CardCategoryKind.BANK_CARD,
        bankName: '招商银行',
        productType: BankCardProductType.DEBIT,
        addedAt: Date.now(),
        huaweiPayEnabled: true,
        unionPayEnabled: true,
        transactions: [tx]
      };
    });

    it('[BRANCH-happy_path][AC-8] insertCard 写入完整字段', 0, async () => {
      const ok: boolean = await repo.insertCard(sampleEntity);
      expect(ok).assertTrue();
      const stored = await repo.queryByCardNumber(sampleEntity.cardNumber);
      expect(stored !== null).assertTrue();
      expect(stored!.bankName).assertEqual('招商银行');
      expect(stored!.transactions.length).assertEqual(1);
    });

    it('[AC-10] queryAllBankCards 返回 RDB 记录', 0, async () => {
      await repo.insertCard(sampleEntity);
      const cards = await repo.queryAllBankCards();
      expect(cards.length).assertEqual(1);
      expect(cards[0].cardNumber).assertEqual(sampleEntity.cardNumber);
    });

    it('[BRANCH-empty_detail_guard][AC-12][BD-2] 空库 count 为 0', 0, async () => {
      const count: number = await repo.countBankCards();
      const cards = await repo.queryAllBankCards();
      expect(count).assertEqual(0);
      expect(cards.length).assertEqual(0);
    });

    it('[BRANCH-persist_fail][BD-1] setForceInsertFail 返回 false', 0, async () => {
      repo.setForceInsertFail(true);
      const ok: boolean = await repo.insertCard(sampleEntity);
      expect(ok).assertFalse();
      const count: number = await repo.countBankCards();
      expect(count).assertEqual(0);
    });
  });
}
