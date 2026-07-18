import openCardFlowTest from './open_card_flow.test';
import smsCountdownTest from './sms_countdown.test';
import bankCardRepositoryTest from './bank_card_repository.test';

export default function testsuite(): void {
  openCardFlowTest();
  smsCountdownTest();
  bankCardRepositoryTest();
}
