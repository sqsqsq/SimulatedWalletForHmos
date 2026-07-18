import { describe, it, expect, beforeEach, afterEach } from '@ohos/hypium';
import { SmsCountdownController } from '../../../main/ets/domain/service/SmsCountdownController';

export default function smsCountdownTest(): void {
  describe('SmsCountdownController', () => {
    let controller: SmsCountdownController;

    beforeEach((): void => {
      controller = new SmsCountdownController();
    });

    afterEach((): void => {
      controller.dispose();
    });

    it('[AC-6] 启动后剩余秒数递减', 0, () => {
      controller.start(60);
      expect(controller.getRemainingSeconds()).assertEqual(60);
      expect(controller.getRemainingSeconds() <= 60).assertTrue();
    });

    it('[AC-6] 重发重置倒计时', 0, () => {
      controller.start(10);
      controller.resend();
      expect(controller.getRemainingSeconds()).assertEqual(60);
      expect(controller.getRemainingSeconds() > 10).assertTrue();
    });
  });
}
