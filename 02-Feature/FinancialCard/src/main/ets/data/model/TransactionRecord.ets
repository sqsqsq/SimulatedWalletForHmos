export interface TransactionRecord {
  id: string;
  merchantName: string;
  amount: number;
  channel: string;
  occurredAt: number;
}
