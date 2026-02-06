create table if not exists customers(
    id serial  primary key,
    first_name varchar(50) not null,
    last_name varchar(50) not null,
    email varchar(100) unique not null,
    created_at timestamptz default current_timestamp
    );

    create table if not exists accounts(
    id serial  primary key,
    customer_id int not null references customers(id) on delete cascade,
    account_type varchar(50) not null,
    balance numeric(15,2) not null default 0 check (balance >= 0),
    currency char(3) not null default 'USD',
    created_at timestamptz default current_timestamp
    
    );

    create table if not exists transactions(
    id bigserial primary key,
    account_id int not null references accounts(id) on delete cascade,
    tnx_type varchar(50) not null,
    amount numeric(15,2) not null,
    related_acc_id int null , 
    status varchar(50) not null default 'completed',
    created_at timestamptz default current_timestamp    
    );

    CREATE INDEX IF NOT EXISTS idx_transactions_account_created ON transactions(account_id, created_at);