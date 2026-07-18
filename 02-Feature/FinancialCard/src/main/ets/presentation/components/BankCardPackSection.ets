import { BankCardEntity } from '../../data/model/BankCardEntity';
import { BankCardRepository } from '../../data/repository/BankCardRepository';
import { BankCardRow } from './BankCardRow';

@Component
export struct BankCardPackSection {
  @State cards: BankCardEntity[] = [];
  @State totalCount: number = 0;
  onCardClick: (cardNumber: string) => void = (_cardNumber: string) => {
  };
  onViewAllClick: () => void = () => {
  };
  private readonly repository: BankCardRepository = BankCardRepository.getInstance();

  aboutToAppear(): void {
    void this.loadCards();
  }

  private async loadCards(): Promise<void> {
    const all: BankCardEntity[] = await this.repository.queryAllBankCards();
    this.totalCount = all.length;
    this.cards = all.slice(0, 2);
  }

  build() {
    if (this.totalCount <= 0) {
      Column()
    } else {
      Column({ space: 8 }) {
        Row() {
          Text($r('app.string.bank_card_section_title'))
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor($r('app.color.token_text_primary'))
            .layoutWeight(1)
          Row({ space: 4 }) {
            Text($r('app.string.view_all_cards'))
              .fontSize(14)
              .fontColor($r('app.color.token_text_secondary'))
            Text(`(${this.totalCount})`)
              .fontSize(14)
              .fontColor($r('app.color.token_text_secondary'))
          }
          .onClick(() => {
            this.onViewAllClick();
          })
        }
        .width('100%')

        ForEach(this.cards, (card: BankCardEntity) => {
          BankCardRow({
            card,
            compact: true,
            onCardClick: () => {
              this.onCardClick(card.cardNumber);
            }
          })
        }, (card: BankCardEntity) => card.cardNumber)
      }
      .width('100%')
    }
  }
}
