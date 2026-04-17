import { CardImageBanner } from '../../shared/components/CardImageBanner';

@Component
export struct CardGuideSection {
  onGoCardPack: () => void = () => {
  };
  onGoAddCard: () => void = () => {
  };

  build() {
    Column({ space: 12 }) {
      CardImageBanner({
        onTap: () => {
          this.onGoCardPack();
        }
      })
      Button($r('app.string.add_manage_cards'), { type: ButtonType.Capsule })
        .width('100%')
        .fontColor(Color.White)
        .backgroundColor($r('app.color.wallet_primary'))
        .onClick(() => {
          this.onGoCardPack();
        })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }
}
