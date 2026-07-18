import { NavPathContext } from '@aspect/CommFunc';
import { getSelectableCardsByProduct, SelectableBankCard } from '../../data/model/BankMockCatalog';
import { OpenCardFlow } from '../../domain/flow/OpenCardFlow';
import { CardNumberMaskUtil } from '../../shared/utils/CardNumberMaskUtil';
import { SmsVerifySheet } from '../sheets/SmsVerifySheet';

@Component
struct SelectBankCardPage {
  @State bankName: string = '';
  @State cards: SelectableBankCard[] = [];
  @State selectedCardId: string = '';
  @State agreed: boolean = false;
  @State sheetVisible: boolean = false;
  private readonly flow: OpenCardFlow = OpenCardFlow.getInstance();

  aboutToAppear(): void {
    const bank = this.flow.state.bank;
    if (bank !== null) {
      this.bankName = bank.name;
      this.cards = getSelectableCardsByProduct(bank.id, this.flow.state.productType);
    }
    if (this.cards.length > 0) {
      this.selectedCardId = this.cards[0].id;
      this.flow.pickCard(this.cards[0]);
    }
  }

  private selectedCard(): SelectableBankCard | null {
    return this.cards.find((card: SelectableBankCard) => card.id === this.selectedCardId) ?? null;
  }

  @Builder
  private smsSheetBuilder() {
    SmsVerifySheet({
      onClose: (): void => {
        this.sheetVisible = false;
      }
    })
  }

  build() {
    NavDestination() {
      Column({ space: 16 }) {
        Text($r('app.string.select_card_hint'))
          .fontSize(14)
          .fontColor($r('app.color.token_text_secondary'))
          .width('100%')
          .padding({ left: 16, right: 16, top: 8 })

        List() {
          ForEach(this.cards, (card: SelectableBankCard) => {
            ListItem() {
              Row() {
                Radio({ value: card.id, group: 'bankCard' })
                  .checked(this.selectedCardId === card.id)
                Text(CardNumberMaskUtil.maskShort(card.fullNumber))
                  .fontSize(16)
                  .fontColor($r('app.color.token_text_primary'))
                  .margin({ left: 8 })
              }
              .width('100%')
              .padding(16)
              .onClick(() => {
                this.selectedCardId = card.id;
                this.flow.pickCard(card);
              })
            }
          }, (card: SelectableBankCard) => card.id)
        }
        .layoutWeight(1)
        .width('100%')

        Column({ space: 12 }) {
          Row() {
            Checkbox({ name: 'agreement', group: 'agreeGroup' })
              .select(this.agreed)
              .onChange((checked: boolean) => {
                this.agreed = checked;
              })
            Text($r('app.string.agreement_checkbox'))
              .fontSize(12)
              .fontColor($r('app.color.token_text_secondary'))
              .margin({ left: 8 })
          }

          Button($r('app.string.next_step'))
            .width('100%')
            .height(44)
            .type(ButtonType.Normal)
            .enabled(this.agreed && this.selectedCard() !== null)
            .backgroundColor(this.agreed ? '#E8EEF8' : '#F1F3F5')
            .fontColor(this.agreed ?
              $r('app.color.token_brand_primary') : $r('app.color.token_text_secondary'))
            .id('next_step_btn')
            .onClick(() => {
              const card: SelectableBankCard | null = this.selectedCard();
              if (card !== null) {
                this.flow.openSmsSheet();
                this.sheetVisible = true;
              }
            })
        }
        .width('100%')
        .padding(16)
      }
      .width('100%')
      .height('100%')
      .backgroundColor($r('app.color.token_bg_page'))
      .bindSheet($$this.sheetVisible, this.smsSheetBuilder(), {
        height: SheetSize.MEDIUM,
        showClose: false,
        dragBar: true
      })
    }
    .title(this.bankName)
    .onBackPressed(() => {
      NavPathContext.stack().pop();
      return true;
    })
  }
}

@Builder
export function buildSelectBankCardPage() {
  SelectBankCardPage();
}
