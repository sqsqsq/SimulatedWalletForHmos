import { describe, it, expect, beforeEach } from '@ohos/hypium';
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

    beforeEach((): void => {
      flow = OpenCardFlow.getInstance();
      flow.reset();
      repo = BankCardRepository.getInstance();
      repo.setForceInsertFail(false);
      spyRepo = new SpyBankCardRepository();
      expect(spyRepo.callLog.length).assertEqual(0);
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
    });

    it('[BRANCH-happy_path][AC-7] 完成开卡后流程重置为 Idle', 0, () => {
      const bank = getMockBankCatalog()[0];
      const card = getSelectableCardsForBank(bank.id)[0];
      flow.openCardTypeSheet(bank);
      flow.confirmCardType(BankCardProductType.DEBIT);
      flow.pickCard(card);
      flow.openSmsSheet();
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
    });
  });
}
