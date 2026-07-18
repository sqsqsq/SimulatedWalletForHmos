import { BankCatalogItem } from '../../data/model/BankMockCatalog';

@Component
export struct BankListItem {
  @Prop bank: BankCatalogItem = {
    id: '',
    name: '',
    pinyinInitial: '',
    logoKey: 'cmb_bank_logo',
    supportsDebit: true,
    supportsCredit: true
  };
  onItemClick: () => void = () => {
  };

  build() {
    Row() {
      Image($r('app.media.cmb_bank_logo'))
        .width(32)
        .height(32)
        .borderRadius(16)
        .margin({ right: 12 })
      Text(this.bank.name)
        .fontSize(16)
        .fontColor($r('app.color.token_text_primary'))
        .layoutWeight(1)
      if (this.bank.promoTag !== undefined && this.bank.promoTag.length > 0) {
        Text($r('app.string.bank_promo_tag'))
          .fontSize(11)
          .fontColor($r('app.color.token_brand_primary'))
          .padding({ left: 6, right: 6, top: 2, bottom: 2 })
          .borderRadius(4)
          .backgroundColor('#1A0A59F7')
          .margin({ right: 8 })
      }
      SymbolGlyph($r('sys.symbol.chevron_right'))
        .fontSize(16)
        .fontColor([$r('app.color.token_text_secondary')])
    }
    .width('100%')
    .padding({ left: 16, right: 16, top: 14, bottom: 14 })
    .backgroundColor($r('app.color.token_bg_surface'))
    .onClick(() => {
      this.onItemClick();
    })
  }
}
