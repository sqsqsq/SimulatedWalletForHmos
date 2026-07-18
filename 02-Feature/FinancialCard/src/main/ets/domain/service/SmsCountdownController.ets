export class SmsCountdownController {
  private remainingSeconds: number = 0;
  private timerId: number = -1;
  private onTick: ((seconds: number) => void) | null = null;

  bindOnTick(callback: (seconds: number) => void): void {
    this.onTick = callback;
  }

  start(initialSeconds: number): void {
    this.clearTimer();
    this.remainingSeconds = initialSeconds;
    this.emitTick();
    this.timerId = setInterval(() => {
      if (this.remainingSeconds > 0) {
        this.remainingSeconds -= 1;
        this.emitTick();
      } else {
        this.clearTimer();
        this.emitTick();
      }
    }, 1000);
  }

  resend(): void {
    this.start(60);
  }

  getRemainingSeconds(): number {
    return this.remainingSeconds;
  }

  dispose(): void {
    this.clearTimer();
    this.onTick = null;
  }

  private emitTick(): void {
    if (this.onTick !== null) {
      this.onTick(this.remainingSeconds);
    }
  }

  private clearTimer(): void {
    if (this.timerId >= 0) {
      clearInterval(this.timerId);
      this.timerId = -1;
    }
  }
}
