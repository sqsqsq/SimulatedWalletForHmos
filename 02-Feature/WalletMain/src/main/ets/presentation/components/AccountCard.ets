import { UserProfile } from '@aspect/AccountManager';

@Component
export struct AccountCard {
  @Prop user: UserProfile = new UserProfile();
  onLoginTap: () => void = () => {
  };

  build() {
    Row() {
      SymbolGlyph($r('sys.symbol.person'))
        .fontSize(40)
        .fontColor([$r('app.color.wallet_primary')])
        .margin({ right: 12 })

      Column({ space: 4 }) {
        Text(this.user.isLoggedIn ? this.user.displayAccount : $r('app.string.not_logged_in'))
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .fontColor($r('app.color.wallet_text_primary'))
        if (!this.user.isLoggedIn) {
          Text($r('app.string.wallet_login_hint'))
            .fontSize(12)
            .fontColor($r('app.color.wallet_text_secondary'))
        }
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1)
    }
    .width('100%')
    .padding(16)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .onClick(() => {
      if (!this.user.isLoggedIn) {
        this.onLoginTap();
      }
    })
  }
}
