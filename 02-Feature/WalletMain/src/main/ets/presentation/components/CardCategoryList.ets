import { Context } from '@kit.AbilityKit';
import { showToast, ActionListItem } from '@aspect/CommUI';
import { CardCategory } from '../../data/model/CardCategory';

@Component
export struct CardCategoryList {
  @Prop categories: CardCategory[] = [];

  build() {
    Column({ space: 0 }) {
      ForEach(this.categories, (item: CardCategory) => {
        Column() {
          ActionListItem({
            icon: item.icon,
            title: item.name,
            onTap: () => {
              const ctx = this.getUIContext().getHostContext() as Context;
              showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
            }
          })
          Text(item.description)
            .fontSize(12)
            .fontColor($r('app.color.wallet_text_secondary'))
            .padding({ left: 16, right: 16, bottom: 8 })
            .width('100%')
        }
      }, (item: CardCategory) => item.id)
    }
    .width('100%')
  }
}
