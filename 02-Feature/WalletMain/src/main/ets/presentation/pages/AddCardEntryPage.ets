import { Context } from '@kit.AbilityKit';
import { NavPathContext } from '@aspect/CommFunc';
import { ActionListItem, showToast } from '@aspect/CommUI';
import { CardCategory } from '../../data/model/CardCategory';
import { CardRepository } from '../../data/repository/CardRepository';
import { CardCategoryList } from '../components/CardCategoryList';

@Component
struct AddCardEntryPage {
  @State categories: CardCategory[] = [];
  @State nonLocalCount: number = 0;
  private readonly cardRepo: CardRepository = new CardRepository();

  private str(res: Resource): string {
    return (this.getUIContext().getHostContext() as Context).resourceManager.getStringSync(res.id);
  }

  aboutToAppear(): void {
    void this.loadAddCardData();
  }

  private async loadAddCardData(): Promise<void> {
    this.categories = await this.cardRepo.getCardCategories();
    this.nonLocalCount = await this.cardRepo.getNonLocalCardCount();
  }

  build() {
    NavDestination() {
      Column({ space: 12 }) {
        Row() {
          Text($r('app.string.non_local_cards'))
            .fontSize(16)
            .fontColor($r('app.color.wallet_text_primary'))
            .layoutWeight(1)
          Text(`${this.nonLocalCount}`)
            .fontSize(12)
            .fontColor(Color.White)
            .width(22)
            .height(22)
            .textAlign(TextAlign.Center)
            .borderRadius(11)
            .backgroundColor($r('app.color.wallet_badge_gray'))
        }
        .width('100%')

        ActionListItem({
          icon: $r('sys.symbol.phone'),
          title: this.str($r('app.string.non_local_cards')),
          onTap: () => {
            const ctx = this.getUIContext().getHostContext() as Context;
            showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
          }
        })

        CardCategoryList({ categories: this.categories })
      }
      .width('100%')
      .height('100%')
      .padding(16)
      .alignItems(HorizontalAlign.Start)
      .backgroundColor($r('app.color.wallet_page_bg'))
    }
    .title($r('app.string.add_card_title'))
    .onBackPressed(() => {
      NavPathContext.stack().pop();
      return true;
    })
  }
}

@Builder
export function buildAddCardEntryPage() {
  AddCardEntryPage();
}
