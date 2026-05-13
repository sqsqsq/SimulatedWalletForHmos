import { Context } from '@kit.AbilityKit';
import { NavPathContext } from '@aspect/CommFunc';
import { ActionListItem, SectionCard, showToast } from '@aspect/CommUI';
import { HomeConstants } from '../../shared/constant/HomeConstants';

@Component
struct CardPackPage {
  private str(res: Resource): string {
    return (this.getUIContext().getHostContext() as Context).resourceManager.getStringSync(res.id);
  }

  build() {
    NavDestination() {
      Column({ space: 12 }) {
        Row() {
          Blank().layoutWeight(1)
          SymbolGlyph($r('sys.symbol.plus'))
            .fontSize(22)
            .fontColor([$r('app.color.wallet_primary')])
            .onClick(() => {
              NavPathContext.stack().pushPath({ name: 'AddCardEntryPage' });
            })
        }
        .width('100%')
        .padding({ right: 8 })

        SectionCard() {
          Row() {
            SymbolGlyph($r('sys.symbol.plus_circle'))
              .fontSize(24)
              .fontColor([$r('app.color.wallet_primary')])
              .margin({ right: 12 })
            Column({ space: 4 }) {
              Text($r('app.string.add_card_title'))
                .fontSize(17)
                .fontWeight(FontWeight.Medium)
                .fontColor($r('app.color.wallet_text_primary'))
                .width('100%')
              Text($r('app.string.add_card_desc'))
                .fontSize(13)
                .fontColor($r('app.color.wallet_text_secondary'))
                .width('100%')
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Start)
            SymbolGlyph($r('sys.symbol.chevron_right'))
              .fontSize(18)
              .fontColor([$r('app.color.wallet_text_secondary')])
          }
          .width('100%')
          .padding({
            left: 12,
            right: 12,
            top: 12,
            bottom: 12
          })
          .onClick(() => {
            NavPathContext.stack().pushPath({ name: 'AddCardEntryPage' });
          })
        }

        if (HomeConstants.SHOW_LOCAL_CARD_SECTION) {
          Column({ space: 8 }) {
            Text($r('app.string.local_cards_section'))
              .fontSize(14)
              .fontColor($r('app.color.wallet_text_secondary'))
              .width('100%')
            Text($r('app.string.local_cards_empty'))
              .fontSize(14)
              .fontColor($r('app.color.wallet_text_secondary'))
              .width('100%')
              .padding(16)
              .backgroundColor(Color.White)
              .borderRadius(12)
          }
        }

        ActionListItem({
          icon: $r('sys.symbol.phone'),
          title: this.str($r('app.string.manage_non_local')),
          onTap: () => {
            const ctx = this.getUIContext().getHostContext() as Context;
            showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
          }
        })
      }
      .width('100%')
      .height('100%')
      .padding(16)
      .alignItems(HorizontalAlign.Start)
      .backgroundColor($r('app.color.wallet_page_bg'))
    }
    .title($r('app.string.card_pack_title'))
    .onBackPressed(() => {
      NavPathContext.stack().pop();
      return true;
    })
  }
}

@Builder
export function buildCardPackPage() {
  CardPackPage();
}
