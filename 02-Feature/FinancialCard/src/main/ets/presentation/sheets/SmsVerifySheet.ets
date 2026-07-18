import { NavPathContext } from '@aspect/CommFunc';
import { BankCardConstants } from '../../shared/constant/BankCardConstants';
import { OpenCardFlow } from '../../domain/flow/OpenCardFlow';
import { SmsCountdownController } from '../../domain/service/SmsCountdownController';

@Component
export struct SmsVerifySheet {
  @State smsCode: string = '';
  @State countdownSec: number = 0;
  onClose: () => void = () => {
  };
  private readonly flow: OpenCardFlow = OpenCardFlow.getInstance();
  private readonly countdown: SmsCountdownController = new SmsCountdownController();

  aboutToAppear(): void {
    this.countdown.bindOnTick((seconds: number) => {
      this.countdownSec = seconds;
    });
    this.countdown.start(BankCardConstants.SMS_COUNTDOWN_SECONDS);
  }

  aboutToDisappear(): void {
    this.countdown.dispose();
  }

  private canSubmit(): boolean {
    return this.smsCode.length === BankCardConstants.SMS_CODE_LENGTH;
  }

  private async submitCode(): Promise<void> {
    await this.flow.submitSmsAndBind(this.smsCode);
    this.onClose();
    NavPathContext.stack().pushPath({ name: 'FinancialCard_AddResult' });
  }

  build() {
    Column({ space: 16 }) {
      Text($r('app.string.sms_verify_title'))
        .fontSize(18)
        .fontWeight(FontWeight.Medium)
        .fontColor($r('app.color.token_text_primary'))
        .width('100%')

      Row({ space: 4 }) {
        Text($r('app.string.sms_verify_hint'))
          .fontSize(14)
          .fontColor($r('app.color.token_text_secondary'))
        Text(BankCardConstants.MOCK_PHONE_MASKED)
          .fontSize(14)
          .fontColor($r('app.color.token_text_primary'))
      }
      .width('100%')

      Row({ space: 8 }) {
        TextInput({ text: this.smsCode, placeholder: '' })
          .type(InputType.Number)
          .maxLength(BankCardConstants.SMS_CODE_LENGTH)
          .layoutWeight(1)
          .onChange((value: string) => {
            this.smsCode = value;
          })
        if (this.countdownSec > 0) {
          Text(`${this.countdownSec}s`)
            .fontSize(14)
            .fontColor($r('app.color.token_text_secondary'))
        } else {
          Text($r('app.string.sms_resend'))
            .fontSize(14)
            .fontColor($r('app.color.token_brand_primary'))
            .onClick(() => {
              this.countdown.resend();
            })
        }
      }
      .width('100%')

      Button($r('app.string.next_step'))
        .width('100%')
        .height(44)
        .type(ButtonType.Normal)
        .enabled(this.canSubmit())
        .backgroundColor(this.canSubmit() ? '#E8EEF8' : '#F1F3F5')
        .fontColor(this.canSubmit() ?
          $r('app.color.token_brand_primary') : $r('app.color.token_text_secondary'))
        .id('sms_next_btn')
        .onClick(() => {
          void this.submitCode();
        })
    }
    .width('100%')
    .padding(16)
    .backgroundColor($r('app.color.token_bg_surface'))
    .id('screen_sms_verify_sheet')
  }
}
