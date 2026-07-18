import { NavPathContext } from '@aspect/CommFunc';
import { OpenCardFlow } from '../../domain/flow/OpenCardFlow';

@Component
struct AddCardResultPage {
  @State success: boolean = true;
  @State cardNumber: string = '';
  private readonly flow: OpenCardFlow = OpenCardFlow.getInstance();

  aboutToAppear(): void {
    this.success = this.flow.state.resultSuccess;
    this.cardNumber = this.flow.state.resultCardNumber;
  }

  private finish(): void {
    this.flow.finishAndPopStack();
    const stack = NavPathContext.stack();
    let guard: number = 0;
    while (guard < 8) {
      stack.pop();
      guard += 1;
    }
    if (this.success) {
      stack.pushPath({ name: 'FinancialCard_BankDetail' });
    }
  }

  build() {
    NavDestination() {
      Column({ space: 16 }) {
        SymbolGlyph(this.success ? $r('sys.symbol.checkmark_circle_fill') : $r('sys.symbol.xmark_circle_fill'))
          .fontSize(64)
          .fontColor([this.success ? '#2BA471' : '#E84026'])
          .margin({ top: 80 })

        Text(this.success ? $r('app.string.result_success_title') : $r('app.string.result_fail_title'))
          .fontSize(22)
          .fontWeight(FontWeight.Medium)
          .fontColor($r('app.color.token_text_primary'))

        Text(this.success ? $r('app.string.result_success_subtitle') : $r('app.string.result_fail_subtitle'))
          .fontSize(14)
          .fontColor($r('app.color.token_text_secondary'))

        Image($r('app.media.add_card_result_illustration'))
          .width('76%')
          .objectFit(ImageFit.Contain)
          .margin({ top: 24 })

        Blank()

        Button($r('app.string.done'))
          .width('90%')
          .height(44)
          .type(ButtonType.Normal)
          .backgroundColor('#E8EEF8')
          .fontColor($r('app.color.token_brand_primary'))
          .id('done_btn')
          .margin({ bottom: 32 })
          .onClick(() => {
            this.finish();
          })
      }
      .width('100%')
      .height('100%')
      .alignItems(HorizontalAlign.Center)
      .backgroundColor($r('app.color.token_bg_page'))
    }
    .hideTitleBar(true)
    .onBackPressed(() => {
      return true;
    })
  }
}

@Builder
export function buildAddCardResultPage() {
  AddCardResultPage();
}
