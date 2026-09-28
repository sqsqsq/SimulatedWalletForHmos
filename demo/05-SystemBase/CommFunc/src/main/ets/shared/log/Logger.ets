import { hilog } from '@kit.PerformanceAnalysisKit';

const DOMAIN = 0xD001000;

export class Logger {
  static debug(tag: string, format: string, ...args: string[]): void {
    hilog.debug(DOMAIN, tag, format, ...args);
  }

  static info(tag: string, format: string, ...args: string[]): void {
    hilog.info(DOMAIN, tag, format, ...args);
  }

  static error(tag: string, format: string, ...args: string[]): void {
    hilog.error(DOMAIN, tag, format, ...args);
  }
}
