import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

import json, datetime
import pandas as pd
import numpy as np

from accounts import *


class DBConnection:
    def __init__(self):
        self.pg_pool = pool.SimpleConnectionPool(20, 100,
                                            database = dbName,
                                            user = dbUser,
                                            password = dbPassword)
    

    @staticmethod
    def transform_data(data):
        """
        Returns a list of tuples of values to insert into DB.
        """
        data = data.replace({np.nan: None, 'None': None})
        values = []
        for i in range(len(data)):
            values.append(tuple(data.iloc[i].values.tolist()))
        return values


    @staticmethod
    def convert_for_json(o):
        if isinstance(o, datetime.datetime):
            return o.__str__().split('+')[0]


    def insert_fb_posts(self, data, transform=True):
        if transform == True:
            data = self.transform_data(data)
        if self.pg_pool:
            conn = self.pg_pool.getconn()
            if conn:
                cur = conn.cursor()
                cur.executemany('INSERT INTO fb_posts VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING', data)
                conn.commit()
                cur.close()
                self.pg_pool.putconn(conn)


    def insert_app_event(self, data, transform=True):
        """
        Log user's actions (session, user_email, time, event, email, group_id)
        """
        if transform == True:
            data = self.transform_data(data)

        if self.pg_pool:
            conn = self.pg_pool.getconn()
            if conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO app_event (session, user_email, time, event, email, group_id) VALUES (%s, %s, %s, %s, %s, %s)", data)
                conn.commit()
                cur.close()
                self.pg_pool.putconn(conn)


    def upsert_user(self, email, password):
        if self.pg_pool:
            conn = self.pg_pool.getconn()
            if conn:
                cur = conn.cursor()
                cur.execute(f"INSERT INTO users (email, password) VALUES ('{email}', '{password}') ON CONFLICT (email) DO UPDATE SET password = EXCLUDED.password")
                conn.commit()
                cur.close()
                self.pg_pool.putconn(conn)


    def get_user(self, email):
        """
        Returns email, password.
        """
        if self.pg_pool:
            conn = self.pg_pool.getconn()
            if conn:
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM users WHERE email = '{email}'")
                userEmail, userPassword = cur.fetchone()
                cur.close()
                self.pg_pool.putconn(conn)
                return userEmail, userPassword


    def get_posts(self, email, _type, fromTime, toTime):
        try:
            # Protect from SQL Injection
            email = email.replace('-','')
            email = email.replace(' ','')
            fromTime = pd.to_datetime(fromTime, format='%Y-%m-%d').strftime('%Y-%m-%d')
            toTime = pd.to_datetime(toTime, format='%Y-%m-%d').strftime('%Y-%m-%d')
            # Then make actual query
            if self.pg_pool:
                conn = self.pg_pool.getconn()
                if conn:
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    cur.execute(f"SELECT * FROM fb_posts \
                        WHERE user_email = '{email}' and \
                        date_trunc('day', imported_time) >= '{fromTime}'::date and \
                        date_trunc('day', imported_time) <= '{toTime}'::date and \
                        type = '{_type.lower()}'")
                    data = json.dumps(cur.fetchall(), default=self.convert_for_json, ensure_ascii=False)
                    cur.close()
                    self.pg_pool.putconn(conn)
                    return data
        except:
            return None


    def get_all_posts(self, email='', _type='', date=None):
        if self.pg_pool:
            conn = self.pg_pool.getconn()
            if conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                if date == None:
                    cur.execute(f"SELECT * FROM fb_posts \
                        WHERE user_email = '{email}'     \
                        AND type = '{_type.lower()}'")
                else:
                    cur.execute(f"SELECT * FROM fb_posts \
                        WHERE user_email = '{email}'     \
                        AND type = '{_type.lower()}'     \
                        AND DATE_TRUNC('day', imported_time) = {date}")
                data = json.dumps(cur.fetchall(), default=self.convert_for_json, ensure_ascii=False)
                cur.close()
                self.pg_pool.putconn(conn)
                return data


    def upsert_old_users(self, data, transform=True):
        if transform == True:
            data = self.transform_data(data)

        if self.pg_pool:
            conn = self.pg_pool.getconn()
            if conn:
                cur = conn.cursor()
                cur.executemany(f"INSERT INTO old_users VALUES (%s) ON CONFLICT DO NOTHING", data)
                conn.commit()
                cur.close()
                self.pg_pool.putconn(conn)


    def get_old_users(self):
        if self.pg_pool:
            conn = self.pg_pool.getconn()
            if conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(f"SELECT * FROM old_users")
                data = json.dumps(cur.fetchall(), default=self.convert_for_json, ensure_ascii=False)
                cur.close()
                self.pg_pool.putconn(conn)
                return data


    def clear_connection(self):
        if self.pg_pool:
            self.pg_pool.closeall()