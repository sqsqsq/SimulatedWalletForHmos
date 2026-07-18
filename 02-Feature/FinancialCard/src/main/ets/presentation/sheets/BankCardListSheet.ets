import { BankCardEntity } from '../../data/model/BankCardEntity';
import { BankCardRepository } from '../../data/repository/BankCardRepository';
import { BankCardRow } from '../components/BankCardRow';

@Component
export struct BankCardListSheet {
  @State cards: BankCardEntity[] = [];
  onClose: () => void = () => {
  };
  onCardClick: (cardNumber: string) => void = (_cardNumber: string) => {
  };
  private readonly repository: BankCardRepository = BankCardRepository.getInstance();

  aboutToAppear(): void {
    void this.loadCards();
  }

  private async loadCards(): Promise<void> {
    this.cards = await this.repository.queryAllBankCards();
  }

  build() {
    Column({ space: 12 }) {
      Row() {
        Text($r('app.string.bank_card_list_title'))
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

      List() {
        ForEach(this.cards, (card: BankCardEntity) => {
          ListItem() {
            BankCardRow({
              card,
              compact: true,
              onCardClick: () => {
                this.onCardClick(card.cardNumber);
              }
            })
          }
        }, (card: BankCardEntity) => card.cardNumber)
      }
      .layoutWeight(1)
      .width('100%')
    }
    .width('100%')
    .height('100%')
    .padding(16)
    .backgroundColor($r('app.color.token_bg_surface'))
    .id('screen_bank_card_list_sheet')
  }
}
