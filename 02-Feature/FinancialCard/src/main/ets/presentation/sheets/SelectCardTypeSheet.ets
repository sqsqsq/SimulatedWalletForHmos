import { NavPathContext } from '@aspect/CommFunc';
import { BankCatalogItem } from '../../data/model/BankMockCatalog';
import { BankCardProductType } from '../../data/model/BankCardEntity';
import { OpenCardFlow } from '../../domain/flow/OpenCardFlow';

@Component
export struct SelectCardTypeSheet {
  @Prop bank: BankCatalogItem | null = null;
  @State selectedType: BankCardProductType = BankCardProductType.DEBIT;
  onClose: () => void = () => {
  };
  private readonly flow: OpenCardFlow = OpenCardFlow.getInstance();

  private confirmCardType(): void {
    if (this.bank === null) {
      return;
    }
    this.flow.confirmCardType(this.selectedType);
    this.onClose();
    NavPathContext.stack().pushPath({ name: 'FinancialCard_SelectBankCard' });
  }

  build() {
    Column({ space: 16 }) {
      Row() {
        Text($r('app.string.select_card_type_title'))
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .fontColor($r('app.color.token_text_primary'))
          .layoutWeight(1)
        SymbolGlyph($r('sys.symbol.xmark'))
          .fontSize(18)
          .fontColor([$r('app.color.token_text_secondary')])
          .onClick(() => {
            this.onClose();
          })
      }
      .width('100%')

      if (this.bank !== null) {
        Row() {
          Image($r('app.media.cmb_bank_logo'))
            .width(40)
            .height(40)
            .borderRadius(20)
            .margin({ right: 12 })
          Text(this.bank.name)
            .fontSize(16)
            .fontColor($r('app.color.token_text_primary'))
        }
        .width('100%')
      }

      Column({ space: 12 }) {
        Row() {
          Radio({ value: BankCardProductType.DEBIT, group: 'cardType' })
            .checked(this.selectedType === BankCardProductType.DEBIT)
            .onChange((checked: boolean) => {
              if (checked) {
                this.selectedType = BankCardProductType.DEBIT;
              }
            })
          Text($r('app.string.debit_card'))
            .fontSize(16)
            .fontColor($r('app.color.token_text_primary'))
            .margin({ left: 8 })
        }
        .width('100%')
        .onClick(() => {
          this.selectedType = BankCardProductType.DEBIT;
        })

        Row() {
          Radio({ value: BankCardProductType.CREDIT, group: 'cardType' })
            .checked(this.selectedType === BankCardProductType.CREDIT)
            .onChange((checked: boolean) => {
              if (checked) {
                this.selectedType = BankCardProductType.CREDIT;
              }
            })
          Text($r('app.string.credit_card'))
            .fontSize(16)
            .fontColor($r('app.color.token_text_primary'))
            .margin({ left: 8 })
        }
        .width('100%')
        .onClick(() => {
          this.selectedType = BankCardProductType.CREDIT;
        })
      }

      Text($r('app.string.card_type_hint'))
        .fontSize(12)
        .fontColor($r('app.color.token_text_secondary'))
        .width('100%')

      Text($r('app.string.agreement_text'))
        .fontSize(12)
        .fontColor($r('app.color.token_text_secondary'))
        .width('100%')

      Button($r('app.string.agree_and_continue'))
        .width('100%')
        .height(44)
        .type(ButtonType.Normal)
        .backgroundColor('#E8EEF8')
        .fontColor($r('app.color.token_brand_primary'))
        .id('agree_continue_btn')
        .onClick(() => {
          this.confirmCardType();
        })
    }
    .width('100%')
    .padding(16)
    .backgroundColor($r('app.color.token_bg_surface'))
    .id('screen_select_card_type_sheet')
  }
}
