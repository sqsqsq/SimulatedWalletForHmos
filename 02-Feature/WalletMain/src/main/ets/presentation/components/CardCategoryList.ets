import { Context } from '@kit.AbilityKit';
import { showToast } from '@aspect/CommUI';
import { CardCategory } from '../../data/model/CardCategory';

@Component
export struct CardCategoryList {
  @Prop categories: CardCategory[] = [];

  private subtitleResFor(item: CardCategory): Resource {
    if (item.id === 'c1') {
      return $r('app.string.add_card_type_bank_subtitle');
    }
    if (item.id === 'c2') {
      return $r('app.string.add_card_type_transit_subtitle');
    }
    if (item.id === 'c3') {
      return $r('app.string.add_card_type_access_subtitle');
    }
    if (item.id === 'c4') {
      return $r('app.string.add_card_type_car_key_subtitle');
    }
    if (item.id === 'c5') {
      return $r('app.string.add_card_type_id_subtitle');
    }
    return $r('app.string.add_card_type_bank_subtitle');
  }

  private iconColorFor(item: CardCategory): Resource {
    if (item.id === 'c1' || item.id === 'c3') {
      return $r('app.color.brand_bank_orange');
    }
    if (item.id === 'c4') {
      return $r('app.color.brand_fuel_green');
    }
    if (item.id === 'c5') {
      return $r('app.color.brand_id_yellow');
    }
    return $r('app.color.brand_primary');
  }

  build() {
    Column() {
      ForEach(this.categories, (item: CardCategory, index: number) => {
        Column() {
          Row() {
            SymbolGlyph(item.icon)
              .fontSize(22)
              .fontColor([this.iconColorFor(item)])
              .margin({ right: 12 })
            Text(item.name)
              .fontSize(16)
              .fontColor($r('app.color.text_primary'))
              .layoutWeight(1)
            Text(this.subtitleResFor(item))
              .fontSize(12)
              .fontColor($r('app.color.text_secondary'))
              .margin({ right: 8 })
            SymbolGlyph($r('sys.symbol.chevron_right'))
              .fontSize(16)
              .fontColor([$r('app.color.text_secondary')])
          }
          .width('100%')
          .padding({
            left: 16,
            right: 16,
            top: 14,
            bottom: 14
          })
          .onClick(() => {
            const ctx = this.getUIContext().getHostContext() as Context;
            showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
          })

          if (index < this.categories.length - 1) {
            Divider()
              .color($r('app.color.text_tertiary'))
              .strokeWidth(0.5)
              .margin({ left: 16, right: 16 })
          }
        }
      }, (item: CardCategory) => item.id)
    }
    .width('100%')
    .backgroundColor($r('app.color.bg_surface'))
    .borderRadius(12)
  }
}
