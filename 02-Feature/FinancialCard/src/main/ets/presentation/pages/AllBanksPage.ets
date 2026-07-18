import { NavPathContext } from '@aspect/CommFunc';
import { BankCatalogItem, getMockBankCatalog } from '../../data/model/BankMockCatalog';
import { OpenCardFlow } from '../../domain/flow/OpenCardFlow';
import { BankListItem } from '../components/BankListItem';
import { SelectCardTypeSheet } from '../sheets/SelectCardTypeSheet';

interface BankSection {
  letter: string;
  banks: BankCatalogItem[];
}

@Component
struct AllBanksPage {
  @State sections: BankSection[] = [];
  @State sheetVisible: boolean = false;
  @State selectedBank: BankCatalogItem | null = null;
  private readonly flow: OpenCardFlow = OpenCardFlow.getInstance();
  private listScroller: Scroller = new Scroller();

  aboutToAppear(): void {
    this.sections = AllBanksPage.buildSections(getMockBankCatalog());
  }

  private static buildSections(banks: BankCatalogItem[]): BankSection[] {
    const map: Map<string, BankCatalogItem[]> = new Map();
    banks.forEach((bank: BankCatalogItem) => {
      const letter: string = bank.pinyinInitial;
      if (!map.has(letter)) {
        map.set(letter, []);
      }
      map.get(letter)?.push(bank);
    });
    const letters: string[] = Array.from(map.keys()).sort();
    return letters.map((letter: string) => ({
      letter,
      banks: map.get(letter) as BankCatalogItem[]
    }));
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
      Stack({ alignContent: Alignment.End }) {
        List({ scroller: this.listScroller }) {
          ForEach(this.sections, (section: BankSection) => {
            ListItemGroup({ header: this.sectionHeaderBuilder(section.letter) }) {
              ForEach(section.banks, (bank: BankCatalogItem) => {
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
          }, (section: BankSection) => section.letter)
        }
        .layoutWeight(1)
        .width('100%')

        Column({ space: 2 }) {
          ForEach(this.sections, (section: BankSection) => {
            Text(section.letter)
              .fontSize(11)
              .fontColor($r('app.color.token_brand_primary'))
              .padding(2)
              .onClick(() => {
                this.listScroller.scrollToIndex(section.letter.charCodeAt(0) % 20);
              })
          }, (section: BankSection) => `idx_${section.letter}`)
        }
        .padding({ right: 4 })
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
    .title($r('app.string.all_banks_title'))
    .onBackPressed(() => {
      NavPathContext.stack().pop();
      return true;
    })
  }

  @Builder
  sectionHeaderBuilder(letter: string) {
    Text(letter)
      .fontSize(13)
      .fontColor($r('app.color.token_text_secondary'))
      .width('100%')
      .padding({ left: 16, top: 8, bottom: 4 })
  }
}

@Builder
export function buildAllBanksPage() {
  AllBanksPage();
}
