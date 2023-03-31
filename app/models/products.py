from .db_base import MySqlBase
from sqlalchemy import Column, String, Integer, TIMESTAMP, JSON


class Products(MySqlBase):

    __tablename__ = 'products'
    id                      = Column(String, primary_key=True)
    fid                     = Column(String)
    marketplace             = Column(String)
    category                = Column(String)
    product_title           = Column(String)