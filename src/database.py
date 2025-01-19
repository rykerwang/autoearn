"""
table operation

id int primary key
created_at datetime
insid varchar(255)
side int
price float
quantity float
available_balance float
diff_balance float
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Operation(Base):
    __tablename__ = 'operation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now())
    insid = Column(String(255))
    side = Column(Integer)
    price = Column(Float)
    quantity = Column(Float)
    available_balance = Column(Float)
    diff_balance = Column(Float)

class Database:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_table(self):
        Base.metadata.create_all(self.engine)

    def tuncat_table(self):
        Base.metadata.drop_all(self.engine)

    def insert_operation(self, operation):
        session = self.Session()
        session.add(operation)
        session.commit()
        session.close()

    def fetch_operations(self):
        session = self.Session()
        operations = session.query(Operation).all()
        session.close()
        return operations

if __name__ == "__main__":
    db = Database("postgresql+psycopg2://autoearn:autoearn@127.0.0.1/autoearn")

    db.create_table()

    # operation = Operation(insid='BTCUSDT', side=1, price=50000, quantity=1, available_balance=10000, diff_balance=1000)
    # db.insert_operation(operation)
    # db.insert_operation('BTCUSDT', 1, 50000, 1, 10000, 1000)
    # db.insert_operation('BTCUSDT', 0, 50000, 1, 10000, 1000)
    # operations = db.fetch_operations()
    # for op in operations:
    #     print(op.id, op.insid, op.side, op.price, op.quantity, op.available_balance, op.diff_balance)