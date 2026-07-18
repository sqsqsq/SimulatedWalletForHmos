import { BankCardEntity, BankCardProductType, CardCategoryKind } from '../../data/model/BankCardEntity';
import { CardNumberMaskUtil } from '../../shared/utils/CardNumberMaskUtil';

@Component
export struct BankCardRow {
  @Prop card: BankCardEntity = {
    cardNumber: '',
    cardCategory: CardCategoryKind.BANK_CARD,
    bankName: '',
    productType: BankCardProductType.DEBIT,
    addedAt: 0,
    huaweiPayEnabled: true,
    unionPayEnabled: true,
    transactions: []
  };
  @Prop compact: boolean = false;
  onCardClick: () => void = () => {
  };

  private productLabelRes(): Resource {
    return this.card.productType === BankCardProductType.CREDIT ?
      $r('app.string.credit_card') : $r('app.string.debit_card');
  }

  build() {
    Row() {
      Image($r('app.media.bank_card_row_thumb'))
        .width(this.compact ? 56 : 72)
        .height(this.compact ? 36 : 46)
        .borderRadius(6)
        .margin({ right: 12 })
      Column({ space: 4 }) {
        Text(this.card.bankName)
          .fontSize(16)
          .fontColor($r('app.color.token_text_primary'))
        Row({ space: 6 }) {
          Text(this.productLabelRes())
            .fontSize(13)
            .fontColor($r('app.color.token_text_secondary'))
          Text(CardNumberMaskUtil.maskShort(this.card.cardNumber))
            .fontSize(13)
            .fontColor($r('app.color.token_text_secondary'))
        }
        Row({ space: 12 }) {
          if (this.card.huaweiPayEnabled) {
            Text($r('app.string.huawei_pay'))
              .fontSize(12)
              .fontColor($r('app.color.token_text_secondary'))
          }
          if (this.card.unionPayEnabled) {
            Text($r('app.string.union_pay'))
              .fontSize(12)
              .fontColor($r('app.color.token_text_secondary'))
          }
        }
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1)
    }
    .width('100%')
    .padding(12)
    .backgroundColor($r('app.color.token_bg_surface'))
    .borderRadius(12)
    .onClick(() => {
      this.onCardClick();
    })
  }
}
