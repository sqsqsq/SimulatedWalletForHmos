import { Context } from '@kit.AbilityKit';
import { showToast } from '@aspect/CommUI';
import { PromoInfo } from '../../data/model/PromoInfo';

@Component
export struct PromoSwiper {
  @Prop promos: PromoInfo[] = [];

  private toastNotSupported(): void {
    const ctx = this.getUIContext().getHostContext() as Context;
    showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
  }

  build() {
    Column({ space: 8 }) {
      Text($r('app.string.more_services'))
        .fontSize(16)
        .fontWeight(FontWeight.Medium)
        .fontColor($r('app.color.wallet_text_primary'))
        .width('100%')

      Swiper() {
        ForEach(this.promos, (item: PromoInfo) => {
          Stack({ alignContent: Alignment.BottomStart }) {
            Row() {
              SymbolGlyph(item.image)
                .fontSize(48)
                .fontColor([$r('app.color.wallet_primary')])
                .margin({ left: 16 })
            }
            .width('100%')
            .height('100%')
            .justifyContent(FlexAlign.Start)
            .alignItems(VerticalAlign.Center)

            Column({ space: 4 }) {
              Text(item.title)
                .fontSize(18)
                .fontWeight(FontWeight.Bold)
                .fontColor($r('app.color.wallet_text_primary'))
              Text(item.description)
                .fontSize(12)
                .fontColor($r('app.color.wallet_text_secondary'))
            }
            .padding(16)
            .width('100%')
          }
          .width('100%')
          .height(140)
          .backgroundColor($r('app.color.promo_placeholder'))
          .borderRadius(12)
          .onClick(() => {
            this.toastNotSupported();
          })
        }, (item: PromoInfo) => item.id)
      }
      .width('100%')
      .autoPlay(true)
      .interval(3000)
      .indicator(true)
    }
    .width('100%')
  }
}
