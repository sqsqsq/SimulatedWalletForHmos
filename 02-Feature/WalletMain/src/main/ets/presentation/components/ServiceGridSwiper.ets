import { Context } from '@kit.AbilityKit';
import { showToast } from '@aspect/CommUI';
import { ServiceEntry } from '../../data/model/ServiceEntry';

@Component
export struct ServiceGridSwiper {
  @Prop services: ServiceEntry[] = [];

  private toastNotSupported(): void {
    const ctx = this.getUIContext().getHostContext() as Context;
    showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
  }

  build() {
    Swiper() {
      Grid() {
        ForEach(this.services, (item: ServiceEntry) => {
          GridItem() {
            Column({ space: 6 }) {
              SymbolGlyph(item.icon)
                .fontSize(32)
                .fontColor([$r('app.color.wallet_primary')])
              Text(item.name)
                .fontSize(12)
                .fontColor($r('app.color.wallet_text_secondary'))
            }
            .width('100%')
            .padding(8)
            .justifyContent(FlexAlign.Center)
            .onClick(() => {
              this.toastNotSupported();
            })
          }
        }, (item: ServiceEntry) => item.id)
      }
      .columnsTemplate('1fr 1fr 1fr')
      .rowsTemplate('1fr')
      .width('100%')
      .height(120)
    }
    .width('100%')
    .autoPlay(false)
    .indicator(true)
  }
}
