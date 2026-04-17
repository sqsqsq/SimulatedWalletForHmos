import { AccountService, LoginState, UserProfile } from '@aspect/AccountManager';
import { ActionListItem, SectionCard, showToast } from '@aspect/CommUI';
import { Context } from '@kit.AbilityKit';
import { FinanceEntry } from '../../data/model/FinanceEntry';
import { SettingEntry } from '../../data/model/SettingEntry';
import { MineRepository } from '../../data/repository/MineRepository';
import { AccountCard } from '../components/AccountCard';

@Component
export struct MineTabPage {
  @State financeList: FinanceEntry[] = [];
  @State settingList: SettingEntry[] = [];
  @State user: UserProfile = new UserProfile();
  private readonly mineRepo: MineRepository = new MineRepository();
  private loginListener: ((state: LoginState) => void) | null = null;

  aboutToAppear(): void {
    void this.loadMineData();
    this.loginListener = (_state: LoginState): void => {
      void this.refreshUser();
    };
    AccountService.getInstance().onLoginStateChanged(this.loginListener);
  }

  aboutToDisappear(): void {
    if (this.loginListener !== null) {
      AccountService.getInstance().offLoginStateChanged(this.loginListener);
    }
  }

  private async loadMineData(): Promise<void> {
    this.financeList = await this.mineRepo.getFinanceEntries();
    this.settingList = await this.mineRepo.getSettingEntries();
    this.user = await AccountService.getInstance().getUserProfile();
  }

  private async refreshUser(): Promise<void> {
    this.user = await AccountService.getInstance().getUserProfile();
  }

  private async handleLogin(): Promise<void> {
    await AccountService.getInstance().login();
    this.user = await AccountService.getInstance().getUserProfile();
  }

  build() {
    Column() {
      Row() {
        Text($r('app.string.mine_title'))
          .fontSize($r('app.float.home_title_size'))
          .fontWeight(FontWeight.Bold)
          .fontColor($r('app.color.wallet_text_primary'))
          .padding({
            left: 16,
            top: 12,
            bottom: 8
          })
      }
      .width('100%')

      Scroll() {
        Column({ space: 16 }) {
          AccountCard({
            user: this.user,
            onLoginTap: (): void => {
              void this.handleLogin();
            }
          })

          Column({ space: 8 }) {
            Text($r('app.string.finance_section_title'))
              .fontSize(14)
              .fontColor($r('app.color.wallet_text_secondary'))
              .width('100%')
              .padding({ left: 4 })
            SectionCard() {
              Column() {
                ForEach(this.financeList, (item: FinanceEntry) => {
                  ActionListItem({
                    icon: item.icon,
                    title: item.name,
                    onTap: () => {
                      const ctx = this.getUIContext().getHostContext() as Context;
                      showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
                    }
                  })
                }, (item: FinanceEntry) => item.id)
              }
            }
          }

          Column({ space: 8 }) {
            Text($r('app.string.settings_section_title'))
              .fontSize(14)
              .fontColor($r('app.color.wallet_text_secondary'))
              .width('100%')
              .padding({ left: 4 })
            SectionCard() {
              Column() {
                ForEach(this.settingList, (item: SettingEntry) => {
                  ActionListItem({
                    icon: item.icon,
                    title: item.name,
                    onTap: () => {
                      const ctx = this.getUIContext().getHostContext() as Context;
                      showToast(ctx.resourceManager.getStringSync($r('app.string.not_supported').id));
                    }
                  })
                }, (item: SettingEntry) => item.id)
              }
            }
          }
        }
        .width('100%')
        .padding({
          left: 16,
          right: 16,
          bottom: 24
        })
      }
      .layoutWeight(1)
      .scrollBar(BarState.Off)
    }
    .width('100%')
    .height('100%')
    .backgroundColor($r('app.color.wallet_page_bg'))
  }
}
