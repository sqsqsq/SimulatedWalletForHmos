import { describe, it, expect, beforeEach, beforeAll } from '@ohos/hypium';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import { OpenCardFlow } from '../../../main/ets/domain/flow/OpenCardFlow';
import { BankCardProductType } from '../../../main/ets/data/model/BankCardEntity';
import { getMockBankCatalog, getSelectableCardsForBank } from '../../../main/ets/data/model/BankMockCatalog';
import { BankCardRepository } from '../../../main/ets/data/repository/BankCardRepository';
import { CardNumberMaskUtil } from '../../../main/ets/shared/utils/CardNumberMaskUtil';
import { SpyBankCardRepository } from './spy/SpyBankCardRepository';

export default function openCardFlowTest(): void {
  describe('OpenCardFlow', () => {
    let flow: OpenCardFlow;
    let repo: BankCardRepository;
    let spyRepo: SpyBankCardRepository;

    beforeAll(async () => {
      repo = BankCardRepository.getInstance();
      const context = abilityDelegatorRegistry.getAbilityDelegator().getAppContext();
      await repo.init(context);
    });

    beforeEach(async (): Promise<void> => {
      flow = OpenCardFlow.getInstance();
      flow.reset();
      repo = BankCardRepository.getInstance();
      repo.setForceInsertFail(false);
      spyRepo = new SpyBankCardRepository();
      spyRepo.whenInsertCard.returns();
      await repo.deleteAllBankCards();
    });

    it('[BRANCH-happy_path][AC-5] 选卡后 session 保留完整卡号', 0, () => {
      const bank = getMockBankCatalog()[0];
      const card = getSelectableCardsForBank(bank.id)[0];
      flow.openCardTypeSheet(bank);
      flow.confirmCardType(BankCardProductType.DEBIT);
      flow.pickCard(card);
      const session = flow.buildSession();
      expect(session.selectedCard.fullNumber).assertEqual(card.fullNumber);
      expect(CardNumberMaskUtil.maskShort(card.fullNumber)).assertContain('****');
      expect(flow.state.phase).assertEqual('CardPicked');
    });

    it('[BRANCH-happy_path][AC-7][AC-8] 短信验证成功写库并进入 Success', 0, async () => {
      const bank = getMockBankCatalog()[0];
      const card = getSelectableCardsForBank(bank.id)[0];
      flow.openCardTypeSheet(bank);
      flow.confirmCardType(BankCardProductType.DEBIT);
      flow.pickCard(card);
      flow.openSmsSheet();
      expect(flow.state.phase).assertEqual('SmsWaiting');
      await flow.submitSmsAndBind('123456');
      expect(flow.state.phase).assertEqual('Success');
      expect(flow.state.resultSuccess).assertTrue();
      const count: number = await repo.countBankCards();
      expect(count).assertEqual(1);
    });

    it('[BRANCH-happy_path][AC-7] 完成开卡后流程重置为 Idle', 0, async () => {
      const bank = getMockBankCatalog()[0];
      const card = getSelectableCardsForBank(bank.id)[0];
      flow.openCardTypeSheet(bank);
      flow.confirmCardType(BankCardProductType.DEBIT);
      flow.pickCard(card);
      flow.openSmsSheet();
      await flow.submitSmsAndBind('123456');
      expect(flow.state.phase).assertEqual('Success');
      flow.finishAndPopStack();
      expect(flow.state.phase).assertEqual('Idle');
      expect(flow.state.bank).assertNull();
    });

    it('[BRANCH-persist_fail][BD-1] 写库失败进入 Failed 态', 0, async () => {
      const bank = getMockBankCatalog()[0];
      const card = getSelectableCardsForBank(bank.id)[0];
      flow.openCardTypeSheet(bank);
      flow.confirmCardType(BankCardProductType.DEBIT);
      flow.pickCard(card);
      flow.openSmsSheet();
      repo.setForceInsertFail(true);
      await flow.submitSmsAndBind('123456');
      expect(flow.state.phase).assertEqual('Failed');
      expect(flow.state.resultSuccess).assertFalse();
      const count: number = await repo.countBankCards();
      expect(count).assertEqual(0);
    });

    it('[BRANCH-empty_detail_guard][AC-12][BD-2] Spy 空库查询记录调用', 0, async () => {
      const cards = await spyRepo.queryAllBankCards();
      expect(cards.length).assertEqual(0);
      expect(spyRepo.callLog).assertDeepEquals(['queryAllBankCards']);
    });
  });
}
