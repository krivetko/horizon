from sqlalchemy import create_engine, MetaData, Table, Integer, String, \
        Column, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, sessionmaker
from datetime import datetime
from util import format_phones
import logging
import random
import openpyxl
# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

engine = create_engine('sqlite:///db/horizon_db')
engine.connect()
session = Session(engine)

Base = declarative_base()

class MyBase(Base):
    __abstract__ = True
    def to_dict(self):
        return {field.name:getattr(self, field.name) for field in self.__table__.c}

class Workers(MyBase):
    __tablename__ = 'workers'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    fio = Column(Text)
    phone = Column(Text)
    engines = Column(Integer, default=0)
    tu = Column(String(2), ForeignKey('tu.id'), nullable=False)
    transactions = relationship('Transactions')
    users = relationship('Users')

class Users(MyBase):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, nullable=False)
    worker_id = Column(Integer, ForeignKey('workers.id'))
    status = Column(Text, nullable=False) #active pending disabled rejected
    wallet = Column(Integer, default=30)
    transactions = relationship('Transactions')

class Transactions(MyBase):
    __tablename__ = 'transactions' 
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    date = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    from_user = Column(Integer, ForeignKey('users.id'))
    to_worker = Column(Integer, ForeignKey('workers.id'))
    reason_id = Column(Integer, ForeignKey('reasons.id'))

class Reasons(MyBase):
    __tablename__ = 'reasons'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    reason = Column(String(100), nullable=False)
    transactions = relationship('Transactions')

class Cheers(MyBase):
    __tablename__ = 'cheers'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    cheer = Column(Text, nullable=False)

class TU(MyBase):
    __tablename__ = 'tu'
    id = Column(String(2), primary_key=True, nullable=False)
    name = Column(Text, nullable=False)
    phone_code = Column(String(3), nullable=False)
    workers = relationship('Workers')

#def init_tu():
#    Base.metadata.create_all(engine, checkfirst=True)
#    tus = [
#        ('84', 'Отделение-НБ Республика Алтай', '202'),
#        ('81', 'Отделение-НБ Республика Бурятия', '210'),
#        ('93', 'Отделение-НБ Республика Тыва', '268'),
#        ('95', 'Отделение-НБ Республика Хакасия', '274'),
#        ('01', 'Отделение Барнаул', '203'),
#        ('76', 'Отделение Чита', '277'),
#        ('25', 'Отделение Иркутск', '219'),
#        ('32', 'Отделение Кемерово', '227'),
#        ('04', 'Отделение Красноярск', '232'),
#        ('52', 'Отделение Омск', '246'),
#        ('69', 'Отделение Томск', '267'),
#        ('50', 'Сибирское ГУ Банка России', '245'),
#    ]
#    for tu in tus:
#        item = TU(
#            id = tu[0],
#            name = tu[1],
#            phone_code = tu[2]
#        )
#        session.add(item)
#        session.commit()

def getUserStatus(id):
    user = session.query(Users).get(id)
    if user:
        return user.status
    else:
        return None

def register_user(user):
    db_user = Users(
        id = user["id"],
        status = "pending"
    )
    session.add(db_user)
    session.commit()
    return None

def reject_user(user):
    db_user = session.query(Users).get(user["id"])
    db_user.status = "rejected"
    session.add(db_user)
    session.commit()
    logger.info(f"Rejected: {user['id']}")
    return None

def get_user_by_worker_id(worker_id):
    user = session.query(Users).filter(Users.worker_id == worker_id).first()
    return user.id

def get_workers(fio):
    found_workers = session.query(Workers.id, Workers.fio, Workers.phone, TU.phone_code, TU.name).filter(Workers.fio.like(f"%{fio}%")).join(TU).all()
    result = []
    for worker in found_workers:
        phone_with_code = '; '.join(map(lambda p: f'({worker[3]}) {p}' if len(p) == 5 else p, [phone.strip() for phone in worker[2].split(';')]))
        result.append(
                { "id": worker[0],
                    "fio": worker[1],
                    #"phone": worker[2],
                    "phone": phone_with_code,
                    "tu": worker[4]
                }
        )
    return result

def get_worker_by_id(id):
    worker = session.query(Workers.id, Workers.fio, Workers.phone, TU.phone_code, TU.name).filter(Workers.id == id).join(TU).first()
    if worker:
        phone_with_code = '; '.join(map(lambda p: f'({worker[3]}) {p}' if len(p) == 5 else p, [phone.strip() for phone in worker[2].split(';')]))
        result = { "id": worker[0],
                    "fio": worker[1],
                    "phone": worker[2],
                    "tu": worker[4]
                }
        return result
    else:
        return None

def set_worker(user_id, worker_id):
    db_user = session.query(Users).get(user_id)
    db_user.worker_id = worker_id
    db_user.status = 'active'
    session.add(db_user)
    session.commit()
    return None

def get_user_name(user_id):
    worker = session.query(Workers.fio).join(Users).filter(Users.id == user_id).first()
    if worker:
        return worker[0]
    else:
        return "Аноним"

def get_wallet(user_id):
    engines = session.query(Users.wallet).filter(Users.id == user_id).first()
    if engines:
        return engines[0]
    else:
        return 0

def get_engines(user_id):
    engines = session.query(Workers.engines).join(Users).filter(Users.id == user_id).first()
    if engines:
        return engines[0]
    else:
        return 0

def get_reasons():
    reasons = session.query(Reasons).all()
    result = []
    for reason in reasons:
        result.append(
            { "text": reason.reason,
                "id": reason.id
            }
        )
    return result

def get_reason_text(id):
    reason = session.query(Reasons.reason).filter(Reasons.id == id).first()
    if reason:
        return reason[0]
    else:
        return ''

def give_engines(user_id, worker_id, reason_id):
    user = session.query(Users).filter(Users.id == user_id).first()
    worker = session.query(Workers).filter(Workers.id == worker_id).first()
    reason = session.query(Reasons).filter(Reasons.id == reason_id).first()
    if user.worker_id == worker_id:
        return [False, 'Нельзя начислить движки самому себе!']
    user.wallet = user.wallet - 10
    session.add(user)
    worker.engines = worker.engines + 10
    session.add(worker)
    today = datetime.today()
    mon_transactions = session.query(Transactions).filter(
            Transactions.from_user == user_id, 
            Transactions.to_worker == worker_id,
            Transactions.month == today.month
    ).count()
    if mon_transactions > 0:
        return [False, 'Нельзя начислять движки коллеге дважды в течение месяца!']
    transaction = Transactions(
        date = today.day, 
        month = today.month,
        year = today.year,
        from_user = user_id,
        to_worker = worker_id, 
        reason_id = reason_id 
    )
    session.add(transaction)
    session.commit()
    return [True,'']

def get_random_cheer():
    rand = random.randrange(0, session.query(Cheers).count())
    return session.query(Cheers.cheer)[rand]

def import_tu(code):
   path = f'db/{code}.xlsx'
   wb = openpyxl.load_workbook(path)
   sh = wb.active
   for row in sh.iter_rows(values_only=True, min_row=2):
        if row[1] == 'NULL':
            continue
        fio_list = [el.strip() for el in (row[1], row[2], row[3]) if el.strip() != '']
        worker = Workers(
                fio = ' '.join(fio_list),
                phone = format_phones(str(row[4])),
                tu = code
        )
        session.add(worker)
        session.commit()
