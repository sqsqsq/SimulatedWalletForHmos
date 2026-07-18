import { Context } from '@kit.AbilityKit';
import { NavPathContext } from '@aspect/CommFunc';
import { showToast } from '@aspect/CommUI';
import { BankCardEntity } from '../../data/model/BankCardEntity';
import { TransactionRecord } from '../../data/model/TransactionRecord';
import { BankCardRepository } from '../../data/repository/BankCardRepository';
import { BankCardFaceCarousel } from '../components/BankCardFaceCarousel';

@Component
struct BankCardDetailPage {
  @State cards: BankCardEntity[] = [];
  @State currentIndex: number = 0;
  private readonly repository: BankCardRepository = BankCardRepository.getInstance();

  aboutToAppear(): void {
    void this.guardEmptyAndExit();
  }

  async guardEmptyAndExit(): Promise<void> {
    this.cards = await this.repository.queryAllBankCards();
    if (this.cards.length === 0) {
      const ctx = this.getUIContext().getHostContext() as Context;
      showToast(ctx.resourceManager.getStringSync($r('app.string.empty_cards_toast').id));
      NavPathContext.stack().pop();
      return;
    }
    this.currentIndex = 0;
  }

  private currentCard(): BankCardEntity {
    return this.cards[this.currentIndex];
  }

  build() {
    NavDestination() {
      Column({ space: 16 }) {
        BankCardFaceCarousel({
          cards: this.cards,
          currentIndex: $currentIndex
        })

        Row({ space: 24 }) {
          this.functionItem($r('app.string.function_transfer'))
          this.functionItem($r('app.string.function_repay'))
          this.functionItem($r('app.string.function_bill'))
          this.functionItem($r('app.string.function_more'))
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceAround)
        .padding(16)
        .backgroundColor($r('app.color.token_bg_surface'))
        .borderRadius(12)

        Column({ space: 8 }) {
          Text($r('app.string.transaction_section_title'))
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor($r('app.color.token_text_primary'))
            .width('100%')
          if (this.currentCard().transactions.length === 0) {
            Text($r('app.string.no_transactions'))
              .fontSize(14)
              .fontColor($r('app.color.token_text_secondary'))
              .width('100%')
              .padding(16)
          } else {
            ForEach(this.currentCard().transactions, (tx: TransactionRecord) => {
              Row() {
                Text(tx.merchantName)
                  .fontSize(14)
                  .fontColor($r('app.color.token_text_primary'))
                  .layoutWeight(1)
                Text(`${tx.amount}`)
                  .fontSize(14)
                  .fontColor($r('app.color.token_text_primary'))
              }
              .width('100%')
              .padding({ top: 8, bottom: 8 })
            }, (tx: TransactionRecord) => tx.id)
          }
        }
        .width('100%')
        .padding(16)
        .backgroundColor($r('app.color.token_bg_surface'))
        .borderRadius(12)

        Column({ space: 8 }) {
          Text($r('app.string.payment_service_title'))
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor($r('app.color.token_text_primary'))
            .width('100%')
          if (this.currentCard().huaweiPayEnabled) {
            this.paymentRow($r('app.string.huawei_pay'))
          }
          if (this.currentCard().unionPayEnabled) {
            this.paymentRow($r('app.string.union_pay'))
          }
        }
        .width('100%')
        .padding(16)
        .backgroundColor($r('app.color.token_bg_surface'))
        .borderRadius(12)
      }
      .width('100%')
      .height('100%')
      .padding(16)
      .backgroundColor($r('app.color.token_bg_page'))
    }
    .title($r('app.string.bank_card_detail_title'))
    .onBackPressed(() => {
      NavPathContext.stack().pop();
      return true;
    })
  }

  @Builder
  functionItem(label: Resource) {
    Column({ space: 4 }) {
      SymbolGlyph($r('sys.symbol.square_grid_2x2'))
        .fontSize(24)
        .fontColor([$r('app.color.token_brand_primary')])
      Text(label)
        .fontSize(12)
        .fontColor($r('app.color.token_text_primary'))
    }
    .onClick(() => {
      const ctx = this.getUIContext().getHostContext() as Context;
      showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
    })
  }

  @Builder
  paymentRow(label: Resource) {
    Row() {
      Text(label)
        .fontSize(14)
        .fontColor($r('app.color.token_text_primary'))
        .layoutWeight(1)
      SymbolGlyph($r('sys.symbol.checkmark'))
        .fontSize(16)
        .fontColor(['#2BA471'])
    }
    .width('100%')
    .padding({ top: 8, bottom: 8 })
    .onClick(() => {
      const ctx = this.getUIContext().getHostContext() as Context;
      showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
    })
  }
}

@Builder
export function buildBankCardDetailPage() {
  BankCardDetailPage();
}
