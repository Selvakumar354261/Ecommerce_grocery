CREATE TABLE branches (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	address VARCHAR(500) NOT NULL, 
	latitude NUMERIC(10, 7) NOT NULL, 
	longitude NUMERIC(10, 7) NOT NULL, 
	radius_km NUMERIC(8, 2) NOT NULL, 
	delivery_fee NUMERIC(12, 2) NOT NULL, 
	active BOOLEAN NOT NULL, 
	accepting_orders BOOLEAN NOT NULL, 
	hours VARCHAR(120) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE login_attempts (
	key VARCHAR(64) NOT NULL, 
	count INTEGER NOT NULL, 
	"window" TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
);

CREATE TABLE products (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	category VARCHAR(80) NOT NULL, 
	description VARCHAR(1000) NOT NULL, 
	tone VARCHAR(20) NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_products_category ON products (category);

CREATE TABLE suppliers (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	phone VARCHAR(30) NOT NULL, 
	address VARCHAR(500) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(180) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	branch_id INTEGER, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);

CREATE TABLE variants (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	sku VARCHAR(60) NOT NULL, 
	label VARCHAR(80) NOT NULL, 
	unit VARCHAR(20) NOT NULL, 
	price NUMERIC(12, 2) NOT NULL, 
	min_qty NUMERIC(14, 3) NOT NULL, 
	step NUMERIC(14, 3) NOT NULL, 
	max_qty NUMERIC(14, 3) NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (price > 0 AND step > 0 AND min_qty > 0 AND max_qty >= min_qty), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	UNIQUE (sku)
);

CREATE INDEX ix_variants_product_id ON variants (product_id);

CREATE TABLE audit (
	id SERIAL NOT NULL, 
	actor_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	reference VARCHAR(100) NOT NULL, 
	details JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE count_requests (
	id SERIAL NOT NULL, 
	branch_id INTEGER NOT NULL, 
	variant_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	approver_id INTEGER, 
	system_quantity NUMERIC(14, 3) NOT NULL, 
	counted_quantity NUMERIC(14, 3) NOT NULL, 
	reason VARCHAR(500) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(variant_id) REFERENCES variants (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	FOREIGN KEY(approver_id) REFERENCES users (id)
);

CREATE TABLE idempotency (
	id SERIAL NOT NULL, 
	actor_id INTEGER NOT NULL, 
	operation VARCHAR(80) NOT NULL, 
	key VARCHAR(100) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	response JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (actor_id, operation, key), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE movements (
	id SERIAL NOT NULL, 
	branch_id INTEGER NOT NULL, 
	variant_id INTEGER NOT NULL, 
	delta NUMERIC(14, 3) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	reference VARCHAR(100) NOT NULL, 
	reason VARCHAR(500) NOT NULL, 
	actor_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(variant_id) REFERENCES variants (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_movements_branch_id ON movements (branch_id);

CREATE TABLE orders (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	branch_id INTEGER NOT NULL, 
	method VARCHAR(20) NOT NULL, 
	address VARCHAR(500) NOT NULL, 
	phone VARCHAR(20) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	payment_status VARCHAR(20) NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	delivery_fee NUMERIC(12, 2) NOT NULL, 
	total NUMERIC(12, 2) NOT NULL, 
	pickup_code VARCHAR(8) NOT NULL, 
	reserved_active BOOLEAN NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);

CREATE INDEX ix_orders_branch_id ON orders (branch_id);

CREATE INDEX ix_orders_created_at ON orders (created_at);

CREATE INDEX ix_orders_user_id ON orders (user_id);

CREATE TABLE purchases (
	id SERIAL NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	branch_id INTEGER NOT NULL, 
	variant_id INTEGER NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	received NUMERIC(14, 3) NOT NULL, 
	unit_cost NUMERIC(12, 2) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(variant_id) REFERENCES variants (id)
);

CREATE TABLE sessions (
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	csrf VARCHAR(80) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_sessions_user_id ON sessions (user_id);

CREATE TABLE shifts (
	id SERIAL NOT NULL, 
	actor_id INTEGER NOT NULL, 
	branch_id INTEGER NOT NULL, 
	opening_cash NUMERIC(12, 2) NOT NULL, 
	counted_cash NUMERIC(12, 2), 
	expected_cash NUMERIC(12, 2), 
	variance NUMERIC(12, 2), 
	opened_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);

CREATE INDEX ix_shifts_actor_id ON shifts (actor_id);

CREATE INDEX ix_shifts_branch_id ON shifts (branch_id);

CREATE TABLE stock (
	id SERIAL NOT NULL, 
	branch_id INTEGER NOT NULL, 
	variant_id INTEGER NOT NULL, 
	on_hand NUMERIC(14, 3) NOT NULL, 
	reserved NUMERIC(14, 3) NOT NULL, 
	damaged NUMERIC(14, 3) NOT NULL, 
	reorder NUMERIC(14, 3) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (branch_id, variant_id), 
	CHECK (on_hand >= 0 AND reserved >= 0 AND damaged >= 0 AND on_hand >= reserved + damaged), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(variant_id) REFERENCES variants (id)
);

CREATE INDEX ix_stock_branch_id ON stock (branch_id);

CREATE INDEX ix_stock_variant_id ON stock (variant_id);

CREATE TABLE transfers (
	id SERIAL NOT NULL, 
	source_id INTEGER NOT NULL, 
	target_id INTEGER NOT NULL, 
	variant_id INTEGER NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	received NUMERIC(14, 3) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	actor_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES branches (id), 
	FOREIGN KEY(target_id) REFERENCES branches (id), 
	FOREIGN KEY(variant_id) REFERENCES variants (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE order_events (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	note VARCHAR(500) NOT NULL, 
	actor_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES orders (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_order_events_order_id ON order_events (order_id);

CREATE TABLE order_items (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	variant_id INTEGER NOT NULL, 
	name VARCHAR(260) NOT NULL, 
	unit VARCHAR(20) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	price NUMERIC(12, 2) NOT NULL, 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES orders (id), 
	FOREIGN KEY(variant_id) REFERENCES variants (id)
);

CREATE INDEX ix_order_items_order_id ON order_items (order_id);

CREATE TABLE sales (
	id SERIAL NOT NULL, 
	branch_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	shift_id INTEGER NOT NULL, 
	total NUMERIC(12, 2) NOT NULL, 
	refunded NUMERIC(12, 2) NOT NULL, 
	payment_method VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	FOREIGN KEY(shift_id) REFERENCES shifts (id)
);

CREATE INDEX ix_sales_branch_id ON sales (branch_id);

CREATE INDEX ix_sales_created_at ON sales (created_at);

CREATE INDEX ix_sales_shift_id ON sales (shift_id);

CREATE TABLE sale_items (
	id SERIAL NOT NULL, 
	sale_id INTEGER NOT NULL, 
	variant_id INTEGER NOT NULL, 
	name VARCHAR(260) NOT NULL, 
	unit VARCHAR(20) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	returned NUMERIC(14, 3) NOT NULL, 
	price NUMERIC(12, 2) NOT NULL, 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(variant_id) REFERENCES variants (id)
);

CREATE INDEX ix_sale_items_sale_id ON sale_items (sale_id);
