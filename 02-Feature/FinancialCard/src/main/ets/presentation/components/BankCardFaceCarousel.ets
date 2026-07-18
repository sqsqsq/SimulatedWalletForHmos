import { BankCardEntity } from '../../data/model/BankCardEntity';

@Component
export struct BankCardFaceCarousel {
  @Prop cards: BankCardEntity[] = [];
  @Link currentIndex: number;
  onIndexChange: (index: number) => void = (_index: number) => {
  };

  build() {
  if (this.cards.length <= 1) {
      Image($r('app.media.bank_card_face_cmb'))
        .width('92%')
        .height(180)
        .borderRadius(16)
        .objectFit(ImageFit.Cover)
    } else {
      Swiper() {
        ForEach(this.cards, (card: BankCardEntity) => {
          Image($r('app.media.bank_card_face_cmb'))
            .width('100%')
            .height(180)
            .borderRadius(16)
            .objectFit(ImageFit.Cover)
        }, (card: BankCardEntity) => card.cardNumber)
      }
      .width('100%')
      .height(200)
      .index(this.currentIndex)
      .itemSpace(12)
      .displayMode(SwiperDisplayMode.STRETCH)
      .prevMargin(24)
      .nextMargin(24)
      .onChange((index: number) => {
        this.currentIndex = index;
        this.onIndexChange(index);
      })
    }
  }
}
