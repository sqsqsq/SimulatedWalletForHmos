// 正例：方向性参数用 start/end，探针应放行。
@Component
export struct Sheet {
  build() {
    Column() { Text('甲') }
      .padding({ start: 16, end: 16, top: 8, bottom: 8 })
  }
}
