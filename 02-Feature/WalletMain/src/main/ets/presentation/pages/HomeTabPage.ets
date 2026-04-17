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
  @Consume('navPathStack') navPathStack: NavPathStack;
  @State services: ServiceEntry[] = [];
  @State promos: PromoInfo[] = [];
  private readonly homeRepo: HomeRepository = new HomeRepository();

  aboutToAppear(): void {
    void this.loadHomeData();
  }

  private async loadHomeData(): Promise<void> {
    this.services = await this.homeRepo.getServiceEntries();
    this.promos = await this.homeRepo.getPromoList();
  }

  build() {
    Column() {
      Row() {
        Text($r('app.string.home_title'))
          .fontSize($r('app.float.home_title_size'))
          .fontWeight(FontWeight.Bold)
          .fontColor($r('app.color.wallet_text_primary'))
          .layoutWeight(1)

        SymbolGlyph($r('sys.symbol.envelope'))
          .fontSize(22)
          .fontColor([$r('app.color.wallet_text_primary')])
          .margin({ right: 16 })
          .onClick(() => {
            const ctx = this.getUIContext().getHostContext() as Context;
            showToast(ctx.resourceManager.getStringSync($r('app.string.msg_center_welcome').id));
          })

        SymbolGlyph($r('sys.symbol.plus'))
          .fontSize(24)
          .fontColor([$r('app.color.wallet_primary')])
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
            },
            onGoAddCard: () => {
              this.navPathStack.pushPath({ name: 'AddCardEntryPage' });
            }
          })

          ServiceGridSwiper({ services: this.services })

          PromoSwiper({ promos: this.promos })
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
