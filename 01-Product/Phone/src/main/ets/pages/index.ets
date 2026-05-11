import { NavPathContext } from '@aspect/CommFunc';
import { buildAddCardEntryPage, buildCardPackPage, HomeTabPage, MineTabPage } from '@aspect/WalletMain';

@Entry
@Component
struct Index {
  @State navPathStack: NavPathStack = new NavPathStack();
  @State currentTabIndex: number = 0;

  aboutToAppear(): void {
    NavPathContext.attach(this.navPathStack);
  }

  @Builder
  navDestinationMap(name: string, _param: Object) {
    if (name === 'CardPackPage') {
      buildCardPackPage();
    } else if (name === 'AddCardEntryPage') {
      buildAddCardEntryPage();
    }
  }

  @Builder
  tabHome() {
    Column() {
      Text($r('app.string.tab_home'))
        .fontSize(12)
        .fontColor(this.currentTabIndex === 0 ? $r('app.color.tab_selected') : $r('app.color.tab_unselected'))
        .margin({ top: 6, bottom: 6 })
    }
    .width('100%')
  }

  @Builder
  tabMine() {
    Column() {
      Text($r('app.string.tab_mine'))
        .fontSize(12)
        .fontColor(this.currentTabIndex === 1 ? $r('app.color.tab_selected') : $r('app.color.tab_unselected'))
        .margin({ top: 6, bottom: 6 })
    }
    .width('100%')
  }

  build() {
    Navigation(this.navPathStack) {
      Tabs({ barPosition: BarPosition.End, index: this.currentTabIndex }) {
        TabContent() {
          HomeTabPage({ navPathStack: $navPathStack })
        }.tabBar(this.tabHome())

        TabContent() {
          MineTabPage()
        }.tabBar(this.tabMine())
      }
      .scrollable(false)
      .barMode(BarMode.Fixed)
      .onChange((index: number) => {
        this.currentTabIndex = index;
      })
      .width('100%')
      .height('100%')
      .backgroundColor($r('app.color.phone_page_bg'))
    }
    .hideTitleBar(true)
    .mode(NavigationMode.Stack)
    .navDestination(this.navDestinationMap)
  }
}
