import { BankCardProductType } from './BankCardEntity';

export interface BankCatalogItem {
  id: string;
  name: string;
  pinyinInitial: string;
  logoKey: string;
  promoTag?: string;
  supportsDebit: boolean;
  supportsCredit: boolean;
}

export interface SelectableBankCard {
  id: string;
  bankId: string;
  productType: BankCardProductType;
  maskedNumber: string;
  fullNumber: string;
}

const BANK_ROWS: Array<[string, string, string]> = [
  ['b01', '招商银行', 'Z'],
  ['b02', '工商银行', 'G'],
  ['b03', '中信银行', 'Z'],
  ['b04', '建设银行', 'J'],
  ['b05', '农业银行', 'N'],
  ['b06', '交通银行', 'J'],
  ['b07', '中国银行', 'Z'],
  ['b08', '民生银行', 'M'],
  ['b09', '光大银行', 'G'],
  ['b10', '兴业银行', 'X'],
  ['b11', '浦发银行', 'P'],
  ['b12', '平安银行', 'P'],
  ['b13', '华夏银行', 'H'],
  ['b14', '广发银行', 'G'],
  ['b15', '北京银行', 'B'],
  ['b16', '上海银行', 'S'],
  ['b17', '浙商银行', 'Z'],
  ['b18', '恒丰银行', 'H'],
  ['b19', '渤海银行', 'B'],
  ['b20', '邮储银行', 'Y']
];

export function getMockBankCatalog(): BankCatalogItem[] {
  return BANK_ROWS.map((row: [string, string, string]) => {
  const item: BankCatalogItem = {
    id: row[0],
    name: row[1],
    pinyinInitial: row[2],
    logoKey: 'cmb_bank_logo',
    supportsDebit: true,
    supportsCredit: true
  };
  if (row[0] === 'b01') {
    item.promoTag = 'promo';
  }
  return item;
  });
}

export function getSelectableCardsForBank(bankId: string): SelectableBankCard[] {
  const suffix: string = bankId.replace('b', '');
  return [
    {
      id: `${bankId}_debit_1`,
      bankId,
      productType: BankCardProductType.DEBIT,
      maskedNumber: `6222 **** **** ${suffix}01`,
      fullNumber: `622200000000${suffix.padStart(4, '0')}01`
    },
    {
      id: `${bankId}_credit_1`,
      bankId,
      productType: BankCardProductType.CREDIT,
      maskedNumber: `4388 **** **** ${suffix}02`,
      fullNumber: `438800000000${suffix.padStart(4, '0')}02`
    }
  ];
}

export function getSelectableCardsByProduct(
  bankId: string,
  productType: BankCardProductType
): SelectableBankCard[] {
  return getSelectableCardsForBank(bankId).filter((card: SelectableBankCard) => card.productType === productType);
}
