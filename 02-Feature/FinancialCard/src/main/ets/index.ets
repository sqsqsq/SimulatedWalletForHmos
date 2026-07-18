import { NavPathContext } from '@aspect/CommFunc';
import { BankCardRepository } from './data/repository/BankCardRepository';
import { buildAddBankCardPage } from './presentation/pages/AddBankCardPage';
import { buildAllBanksPage } from './presentation/pages/AllBanksPage';
import { buildSelectBankCardPage } from './presentation/pages/SelectBankCardPage';
import { buildAddCardResultPage } from './presentation/pages/AddCardResultPage';
import { buildBankCardDetailPage } from './presentation/pages/BankCardDetailPage';
import { BankCardPackSection } from './presentation/components/BankCardPackSection';

export { BankCardPackSection } from './presentation/components/BankCardPackSection';
export { BankCardRepository } from './data/repository/BankCardRepository';
export { OpenCardFlow } from './domain/flow/OpenCardFlow';

export function openAddBankCard(_stack?: NavPathStack): void {
  NavPathContext.stack().pushPath({ name: 'FinancialCard_AddBankCard' });
}

export async function initFinancialCard(context: Context): Promise<void> {
  await BankCardRepository.getInstance().init(context);
}

export { buildAddBankCardPage, buildAllBanksPage, buildSelectBankCardPage, buildAddCardResultPage, buildBankCardDetailPage };
