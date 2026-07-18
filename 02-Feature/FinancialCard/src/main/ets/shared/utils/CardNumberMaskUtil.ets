export class CardNumberMaskUtil {
  static mask(cardNumber: string): string {
    if (cardNumber.length <= 8) {
      return cardNumber;
    }
    const prefix: string = cardNumber.substring(0, 4);
    const suffix: string = cardNumber.substring(cardNumber.length - 4);
    return `${prefix} **** **** ${suffix}`;
  }

  static maskShort(cardNumber: string): string {
    if (cardNumber.length <= 8) {
      return cardNumber;
    }
    return `${cardNumber.substring(0, 4)} **** ${cardNumber.substring(cardNumber.length - 4)}`;
  }
}
