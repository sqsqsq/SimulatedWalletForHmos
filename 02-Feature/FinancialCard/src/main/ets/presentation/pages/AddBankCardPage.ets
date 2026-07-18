import { NavPathContext } from '@aspect/CommFunc';
import { BankCatalogItem, getMockBankCatalog } from '../../data/model/BankMockCatalog';
import { OpenCardFlow } from '../../domain/flow/OpenCardFlow';
import { BankListItem } from '../components/BankListItem';
import { SelectCardTypeSheet } from '../sheets/SelectCardTypeSheet';

@Component
struct AddBankCardPage {
  @State isExpanded: boolean = false;
  @State banks: BankCatalogItem[] = [];
  @State sheetVisible: boolean = false;
  @State selectedBank: BankCatalogItem | null = null;
  private readonly flow: OpenCardFlow = OpenCardFlow.getInstance();

  aboutToAppear(): void {
    this.banks = getMockBankCatalog();
    this.flow.reset();
  }

  private visibleBankCount(): number {
    return this.isExpanded ? this.banks.length : Math.min(5, this.banks.length);
  }

  private footerBanks(): BankCatalogItem[] {
    const start: number = this.visibleBankCount();
    return this.banks.slice(start, start + 5);
  }

  private openBankSheet(bank: BankCatalogItem): void {
    this.selectedBank = bank;
    this.flow.openCardTypeSheet(bank);
    this.sheetVisible = true;
  }

  @Builder
  private cardTypeSheetBuilder() {
    SelectCardTypeSheet({
      bank: this.selectedBank,
      onClose: (): void => {
        this.sheetVisible = false;
      }
    })
  }

  build() {
    NavDestination() {
      Column() {
        List() {
          ListItem() {
            Column({ space: 4 }) {
              Text($r('app.string.add_bank_subtitle_main'))
                .fontSize(14)
                .fontColor($r('app.color.token_text_secondary'))
              Text($r('app.string.add_bank_subtitle_count'))
                .fontSize(14)
                .fontColor($r('app.color.token_text_secondary'))
            }
            .width('100%')
            .padding({ left: 16, right: 16, top: 8, bottom: 8 })
            .alignItems(HorizontalAlign.Start)
          }

          ForEach(this.banks.slice(0, this.visibleBankCount()), (bank: BankCatalogItem) => {
            ListItem() {
              BankListItem({
                bank,
                onItemClick: () => {
                  this.openBankSheet(bank);
                }
              })
            }
          }, (bank: BankCatalogItem) => bank.id)
        }
        .layoutWeight(1)
        .width('100%')
        .backgroundColor($r('app.color.token_bg_page'))

        Column({ space: 8 }) {
          Row({ space: 8 }) {
            ForEach(this.footerBanks(), (_bank: BankCatalogItem, index: number) => {
              Image($r('app.media.cmb_bank_logo'))
                .width(28)
                .height(28)
                .borderRadius(14)
            }, (_bank: BankCatalogItem, index: number) => `footer_${index}`)
          }
          .justifyContent(FlexAlign.Center)
          .width('100%')

          if (!this.isExpanded) {
            Text($r('app.string.more_banks'))
              .fontSize(14)
              .fontColor($r('app.color.token_brand_primary'))
              .onClick(() => {
                this.isExpanded = true;
              })
          } else {
            Text($r('app.string.view_all_banks'))
              .fontSize(14)
              .fontColor($r('app.color.token_brand_primary'))
              .onClick(() => {
                NavPathContext.stack().pushPath({ name: 'FinancialCard_AllBanks' });
              })
          }
        }
        .width('100%')
        .padding({ top: 12, bottom: 24 })
        .backgroundColor($r('app.color.token_bg_page'))
      }
      .width('100%')
      .height('100%')
      .backgroundColor($r('app.color.token_bg_page'))
      .bindSheet($$this.sheetVisible, this.cardTypeSheetBuilder(), {
        height: SheetSize.MEDIUM,
        showClose: false,
        dragBar: true
      })
    }
    .title($r('app.string.add_bank_card_title'))
    .onBackPressed(() => {
      NavPathContext.stack().pop();
      return true;
    })
  }
}

@Builder
export function buildAddBankCardPage() {
  AddBankCardPage();
}
