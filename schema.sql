PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id INTEGER UNIQUE NOT NULL,
  username TEXT,
  full_name TEXT,
  role TEXT NOT NULL DEFAULT 'user', -- user, support, admin, owner
  is_banned INTEGER NOT NULL DEFAULT 0,
  tos_version_accepted INTEGER,
  is_reseller INTEGER NOT NULL DEFAULT 0,
  reseller_discount_percent REAL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wallets (
  user_id INTEGER PRIMARY KEY,
  balance_usd REAL NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wallet_tx (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  tx_type TEXT NOT NULL, -- deposit,purchase,refund,manual_add,manual_deduct
  direction TEXT NOT NULL, -- credit,debit
  amount_usd REAL NOT NULL,
  method TEXT,
  ref_id TEXT,
  note TEXT,
  created_by INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  price_usd REAL NOT NULL,
  reseller_price_usd REAL,
  is_active INTEGER NOT NULL DEFAULT 1,
  show_stock INTEGER NOT NULL DEFAULT 1,
  stock_count INTEGER NOT NULL DEFAULT 0,
  low_stock_threshold INTEGER NOT NULL DEFAULT 5,
  post_delivery_enabled INTEGER NOT NULL DEFAULT 0,
  post_delivery_text TEXT,
  post_delivery_parse_mode TEXT DEFAULT 'HTML',
  post_delivery_media_type TEXT DEFAULT 'none',
  post_delivery_media_file_id TEXT,
  post_delivery_media_caption TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_units (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL,
  unit_type TEXT NOT NULL, -- text, file
  payload_text TEXT,
  file_id TEXT,
  watermark_template TEXT,
  is_sold INTEGER NOT NULL DEFAULT 0,
  sold_to_user_id INTEGER,
  sold_order_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sold_at TEXT,
  FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  pricing_tier TEXT NOT NULL DEFAULT 'retail', -- retail,reseller
  gross_usd REAL NOT NULL,
  discount_usd REAL NOT NULL DEFAULT 0,
  net_usd REAL NOT NULL,
  coupon_code TEXT,
  status TEXT NOT NULL DEFAULT 'created', -- created,delivered,failed,refunded
  receipt_id TEXT UNIQUE NOT NULL,
  delivered_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS deliveries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  step TEXT NOT NULL, -- credential, post_text, post_media
  attempt_no INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'queued', -- queued,ok,failed
  error_msg TEXT,
  queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at TEXT,
  FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payment_methods (
  code TEXT PRIMARY KEY, -- stripe,tg,binance_pay,crypto,upi,binance_id
  is_enabled INTEGER NOT NULL DEFAULT 0,
  mode TEXT NOT NULL DEFAULT 'manual', -- auto,manual
  config_json TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS coupons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL, -- fixed,percent
  value REAL NOT NULL,
  min_order_usd REAL DEFAULT 0,
  max_total_uses INTEGER,
  max_per_user INTEGER,
  used_count INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS coupon_redemptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  coupon_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  discount_usd REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS disputes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', -- open,closed,rejected
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(order_id) REFERENCES orders(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS broadcasts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_text TEXT NOT NULL,
  schedule_at TEXT, -- null = instant
  status TEXT NOT NULL DEFAULT 'queued', -- queued,sent,failed
  sent_count INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0,
  created_by INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value_json TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_user_id INTEGER,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  meta_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proofs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  proof_type TEXT NOT NULL, -- delivery
  message_id INTEGER,
  data_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(order_id) REFERENCES orders(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS backups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ok',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO payment_methods(code,is_enabled,mode) VALUES
('stripe',0,'auto'),
('tg',0,'auto'),
('binance_pay',0,'auto'),
('crypto',0,'auto'),
('upi',1,'manual'),
('binance_id',1,'manual');
