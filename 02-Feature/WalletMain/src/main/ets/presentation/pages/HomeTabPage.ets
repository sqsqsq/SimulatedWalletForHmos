import { Context } from '@kit.AbilityKit';
import { showToast } from '@aspect/CommUI';
import { HomeRepository } from '../../data/repository/HomeRepository';
import { HomeLoadingUseCase, HomePhase } from '../../domain/usecase/HomeLoadingUseCase';
import { PromoInfo } from '../../data/model/PromoInfo';
import { ServiceEntry } from '../../data/model/ServiceEntry';
import { CardGuideSection } from '../components/CardGuideSection';
import { PromoSwiper } from '../components/PromoSwiper';
import { ServiceGridSwiper } from '../components/ServiceGridSwiper';

/**
 * HomeTabPage — 订阅 HomeLoadingUseCase 状态并翻译为副作用（Toast / 渲染）。
 * 业务流程由 UseCase 承担，UI 层只负责：
 * 1) 在 aboutToAppear 触发 useCase.onAppear()；
 * 2) 把 state.phase / services / promos 映射到 @State 并驱动渲染；
 * 3) state.phase === Failed 时翻译为 Toast。
 */
@Component
export struct HomeTabPage {
  @Consume('navPathStack') navPathStack: NavPathStack;
  @State services: ServiceEntry[] = [];
  @State promos: PromoInfo[] = [];
  @State phase: HomePhase = HomePhase.Idle;
  private readonly useCase: HomeLoadingUseCase = new HomeLoadingUseCase(new HomeRepository());

  aboutToAppear(): void {
    void this.triggerLoad();
  }

  private async triggerLoad(): Promise<void> {
    await this.useCase.onAppear();
    this.phase = this.useCase.state.phase;
    this.services = this.useCase.state.services;
    this.promos = this.useCase.state.promos;
    if (this.phase === HomePhase.Failed) {
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
