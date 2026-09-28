// 反例：方向性布局参数写成 left/right——探针必须报出来。
@Component
export struct Sheet {
  build() {
    Column() { Text('甲') }
      .padding({ left: 16, right: 16, top: 8, bottom: 8 })
  }
}
