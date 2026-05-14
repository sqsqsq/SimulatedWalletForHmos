import { Context } from '@kit.AbilityKit';
import { showToast } from '@aspect/CommUI';
import { HomeRepository } from '../../data/repository/HomeRepository';
import { PromoInfo } from '../../data/model/PromoInfo';
import { ServiceEntry } from '../../data/model/ServiceEntry';
import { CardGuideSection } from '../components/CardGuideSection';
import { PromoSwiper } from '../components/PromoSwiper';
import { ServiceGridSwiper } from '../components/ServiceGridSwiper';

@Component
export struct HomeTabPage {
  /** NavPathStack 禁止 @Prop（真机 pushPath 会丢原生句柄 SIGSEGV），须与 Navigation 同源 @Link */
  @Link navPathStack: NavPathStack;
  @State services: ServiceEntry[] = [];
  @State promos: PromoInfo[] = [];
  private readonly homeRepo: HomeRepository = new HomeRepository();

  aboutToAppear(): void {
    void this.loadHomeData();
  }

  private async loadHomeData(): Promise<void> {
    try {
      this.services = await this.homeRepo.getServiceEntries();
      this.promos = await this.homeRepo.getPromoList();
    } catch {
      this.services = [];
      this.promos = [];
      const ctx = this.getUIContext().getHostContext() as Context;
      showToast(ctx.resourceManager.getStringSync($r('app.string.home_data_unavailable').id));
    }
  }

  build() {
    Column() {
      Row() {
        Text($r('app.string.home_title'))
          .fontSize($r('app.float.home_title_size'))
          .fontWeight(FontWeight.Bold)
          .fontColor($r('app.color.wallet_text_primary'))
          .layoutWeight(1)

        Text($r('app.string.home_header_msg_action'))
          .fontSize(14)
          .fontColor($r('app.color.wallet_primary'))
          .margin({ right: 12 })
          .onClick(() => {
            const ctx = this.getUIContext().getHostContext() as Context;
            showToast(ctx.resourceManager.getStringSync($r('app.string.msg_center_welcome').id));
          })

        Text($r('app.string.home_title_add_action'))
          .fontSize(26)
          .fontWeight(FontWeight.Medium)
          .fontColor($r('app.color.wallet_primary'))
          .onClick(() => {
            this.navPathStack.pushPath({ name: 'AddCardEntryPage' });
          })
      }
      .width('100%')
      .padding({
        left: 16,
        right: 16,
        top: 12,
        bottom: 8
      })

      Scroll() {
        Column({ space: 16 }) {
          CardGuideSection({
            onGoCardPack: () => {
              this.navPathStack.pushPath({ name: 'CardPackPage' });
            }
          })

          if (this.services.length > 0) {
            ServiceGridSwiper({ services: this.services })
          }

          if (this.promos.length > 0) {
            PromoSwiper({ promos: this.promos })
          }
        }
        .width('100%')
        .padding({
          left: 16,
          right: 16,
          bottom: 24
        })
      }
      .layoutWeight(1)
      .scrollBar(BarState.Off)
    }
    .width('100%')
    .height('100%')
    .backgroundColor($r('app.color.wallet_page_bg'))
  }
}
